# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The HTTP conformance exchanges a server answers or a client sends.

The runner supplies each client action and the complete server action table as
JSON. Both sides of the domain use it:

- A **server** scenario is a plain server process. It declares matching routes
    with the framework under test, listens on the port in
    ``OTEL_HTTP_SCENARIO_PORT``, and stays up until its standard input closes;
    ``otel-http-drive`` starts it and sends requests at it from outside,
    then closes standard input so it flushes and exits.
- A **client** scenario is the sender. It passes its own library as ``send``
  to :func:`drive_selected`, pointed at a server the runner started — see
  ``tools/http/mock-server``, which answers the injected action table.

Nothing under test ever drives a server scenario: the driver is a separate
process, so no instrumentation loaded into the scenario can pick the driver up
and record client spans the scenario never meant to produce.

The external server driver checks every response against its exchange. A
server scenario declares routes in its framework's native form — that
declaration is what an instrumentation reads a route from — but every status
and body is a constant from the shared file because the requests are fixed.

Only ``otel-http-drive`` reads the canonical YAML contract, and only when no
runner gave it a table. Workloads never discover or load it.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Awaitable
from functools import lru_cache
from typing import Callable, Mapping, NamedTuple, NoReturn, Sequence, cast
from wsgiref.simple_server import WSGIRequestHandler, make_server

__all__ = [
    "ACTIONS_VARIABLE",
    "ACTION_VARIABLE",
    "CONTENT_TYPE",
    "PORT_VARIABLE",
    "PROTOCOL_VARIABLE",
    "REQUEST_TIMEOUT_SECONDS",
    "USER_AGENT",
    "AsyncSend",
    "ContractError",
    "Exchange",
    "Send",
    "client_headers",
    "drive",
    "drive_all",
    "drive_async",
    "drive_selected",
    "drive_selected_async",
    "mock_server_url",
    "request",
    "reserve_port",
    "respond",
    "scenario_port",
    "scenario_request",
    "serve",
    "verify",
    "wait_for_health",
    "wait_for_port",
]


class ContractError(AssertionError):
    """A server answered something the contract does not describe."""


class Exchange(NamedTuple):
    """One concrete request and the answer the contract requires."""

    method: str
    path: str
    body: str | None
    status: int
    response_body: str
    readiness: bool
    # The request's role in the contract, including readiness or the telemetry
    # behavior it exercises. Shared so every language reads the same description.
    description: str


# How one request is sent: method, absolute URL, body → status, response body.
# A client scenario supplies its own so its library is the one instrumented.
Send = Callable[[str, str, "str | None"], "tuple[int, str]"]
AsyncSend = Callable[[str, str, "str | None"], Awaitable["tuple[int, str]"]]

# The port a server scenario listens on. ``otel-http-drive`` chooses it, which
# is what lets different scenarios run in parallel without colliding.
PORT_VARIABLE = "OTEL_HTTP_SCENARIO_PORT"
ACTION_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTION"
ACTIONS_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTIONS"

# Set by the runner only when the contract's driver role made this run
# persistent, which is how ``otel-http-drive --serve`` learns it is being
# driven rather than sending one pass of its own.
PROTOCOL_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_PROTOCOL"

# Fixed rather than the interpreter's default, so a server scenario is driven
# by the same client whichever Python happens to be installed.
USER_AGENT = "otel-http-conformance/1"

_HEALTH_POLL_SECONDS = 0.05
REQUEST_TIMEOUT_SECONDS = 10


# Every route answers JSON, so a scenario that reads the contract has one
# content type to send rather than a rule per route.
CONTENT_TYPE = "application/json"


def mock_server_url() -> str:
    """The mock server URL the runner gave a client scenario."""
    base_url = os.environ.get("MOCK_SERVER_URL")
    if not base_url:
        raise RuntimeError(
            "MOCK_SERVER_URL is not set — the runner publishes it for the "
            "server the package declares"
        )
    return base_url


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON constant {value}")


def _decode_json(raw: str, variable: str) -> object:
    try:
        return json.loads(raw, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(
            f"{variable} contains malformed JSON: {error}"
        ) from error


def _check_keys(
    value: Mapping[str, object],
    allowed: set[str],
    where: str,
) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise RuntimeError(f"{where} has unknown field(s): {unknown}")


def _exchange_from_action(
    value: object,
    *,
    variable: str,
    readiness: bool,
) -> Exchange:
    where = f"{variable} action"
    if not isinstance(value, dict):
        raise RuntimeError(f"{where} must be a JSON object")
    action = cast(dict[str, object], value)
    _check_keys(action, {"request", "response"}, where)
    if set(action) != {"request", "response"}:
        raise RuntimeError(f"{where} requires request and response objects")

    request_value = action["request"]
    response_value = action["response"]
    if not isinstance(request_value, dict):
        raise RuntimeError(f"{where}.request must be a JSON object")
    if not isinstance(response_value, dict):
        raise RuntimeError(f"{where}.response must be a JSON object")
    request = cast(dict[str, object], request_value)
    response = cast(dict[str, object], response_value)
    _check_keys(request, {"method", "path", "body"}, f"{where}.request")
    _check_keys(response, {"status", "body"}, f"{where}.response")

    method = request.get("method")
    path = request.get("path")
    body = request.get("body")
    status = response.get("status")
    response_body = response.get("body")
    if not isinstance(method, str) or not method:
        raise RuntimeError(
            f"{where}.request.method must be a non-empty string"
        )
    if not isinstance(path, str) or not path.startswith("/"):
        raise RuntimeError(f"{where}.request.path must start with '/'")
    if body is not None and not isinstance(body, str):
        raise RuntimeError(f"{where}.request.body must be a string")
    if (
        not isinstance(status, int)
        or isinstance(status, bool)
        or not 100 <= status <= 599
    ):
        raise RuntimeError(f"{where}.response.status must be an HTTP status")
    if not isinstance(response_body, str):
        raise RuntimeError(f"{where}.response.body must be a string")
    return Exchange(
        method,
        path,
        body,
        status,
        response_body,
        readiness,
        "runner readiness action" if readiness else "runner action",
    )


def _decode_action_table(raw: str) -> tuple[Exchange, ...]:
    """Decode the runner's action table. Explicit input, no cache."""

    loaded = _decode_json(raw, ACTIONS_VARIABLE)
    if not isinstance(loaded, list) or not loaded:
        raise RuntimeError(
            f"{ACTIONS_VARIABLE} must be a non-empty JSON array of actions"
        )
    actions = cast(list[object], loaded)
    return tuple(
        _exchange_from_action(
            action,
            variable=f"{ACTIONS_VARIABLE}[{index}]",
            readiness=index == 0,
        )
        for index, action in enumerate(actions)
    )


@lru_cache(maxsize=None)
def _cached_action_table(raw: str) -> tuple[Exchange, ...]:
    return _decode_action_table(raw)


def _action_table(raw: str | None = None) -> tuple[Exchange, ...]:
    """The runner's action table, parsed once per measured process.

    A server scenario answers every request from this table, so decoding it
    per request would charge the measured process for JSON parsing on the
    very path its instrumentation is timing. The table arrives once in the
    environment and never changes, so its parse is keyed by that text.
    """

    if raw is None:
        raw = os.environ.get(ACTIONS_VARIABLE)
    if raw is None:
        raise RuntimeError(f"{ACTIONS_VARIABLE} is not set")
    return _cached_action_table(raw)


def scenario_request(raw: str | None = None) -> Exchange:
    """Decode the one request selected by the runner."""
    if raw is None:
        raw = os.environ.get(ACTION_VARIABLE)
    if raw is None:
        raise RuntimeError(f"{ACTION_VARIABLE} is not set")
    return _exchange_from_action(
        _decode_json(raw, ACTION_VARIABLE),
        variable=ACTION_VARIABLE,
        readiness=False,
    )


def client_headers(body: str | None) -> dict[str, str]:
    """The fixed headers every client workload sends."""
    headers = {"User-Agent": USER_AGENT}
    if body is not None:
        headers["Content-Type"] = CONTENT_TYPE
    return headers


def _exchange_for(method: str, path: str) -> Exchange | None:
    """The concrete exchange answering ``method path``, if there is one."""
    path = path.split("?", 1)[0]
    for exchange in _action_table():
        if (
            exchange.method == method
            and exchange.path.split("?", 1)[0] == path
        ):
            return exchange
    return None


def _canonical_json(value: object) -> str:
    """``value`` written so that only its JSON content can differ.

    Sorting keys and dropping insignificant whitespace makes two documents
    compare equal exactly when they carry the same JSON, and writing them
    back out keeps ``1`` and ``true`` apart, which Python's ``==`` does not.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _carries_the_contracts_body(exchange: Exchange, body: str | None) -> bool:
    """Whether ``body`` is the body the contract's request sends.

    Parsed rather than compared as text: how a client library spaces and
    orders its JSON is its own business. A request the contract declares
    without a body carries whatever arrived, since nothing describes it.
    """
    if exchange.body is None:
        return True
    try:
        got, want = json.loads(body or ""), json.loads(exchange.body)
    except json.JSONDecodeError:
        return False
    return _canonical_json(got) == _canonical_json(want)


def respond(
    method: str,
    path: str,
    body: str | None = None,
    *,
    check_request_body: bool = False,
) -> tuple[int, str]:
    """What the contract answers to one request.

    The whole answer contract in one function, so the mock server a client
    scenario calls and any Python server scenario answer identically.

    ``check_request_body`` answers 400 when a request the contract declares
    with a body arrives without that body. Only the mock server asks for
    that. A server scenario's answers are read by :func:`verify`, which
    compares the echoed body and so already fails a scenario that never read
    the request; the answer a client scenario receives is read by nothing, so
    a client that never sent the body would otherwise be echoed an empty
    payload and pass.
    """
    exchange = _exchange_for(method, path)
    if exchange is None:
        return 404, '{"message": "no such route"}'
    if check_request_body and not _carries_the_contracts_body(exchange, body):
        return 400, '{"message": "not the body the contract sends"}'
    return exchange.status, exchange.response_body.replace(
        "${requestBody}", body or "{}"
    )


def drive(
    base_url: str,
    send: Send | None = None,
) -> None:
    """Send and verify every measured request.

    This is the original public driver. Indexed client scenarios use
    :func:`drive_selected` instead.
    """
    drive_all(base_url, send)


def drive_selected(
    base_url: str,
    send: Send | None = None,
) -> None:
    """Send the runner-selected request at ``base_url``.

    ``send`` defaults to the standard library. A client scenario passes its
    own library instead — that call is the thing being measured.

    The server is assumed to be up: waiting is :func:`wait_for_health`, kept
    separate because every extra request a driver makes while a server starts
    is a span in that server's report.

    The returned status and body are logged for diagnostics. Telemetry is the
    conformance result.
    """
    sender = send or request
    exchange = scenario_request()
    status, response = sender(
        exchange.method,
        f"{base_url}{exchange.path}",
        exchange.body,
    )
    print(f"{exchange.method} {exchange.path} -> {status} {response[:60]}")


def drive_all(base_url: str, send: Send | None = None) -> None:
    """Send and verify every measured request when driving a server scenario."""
    _drive_exchanges(base_url, _action_table()[1:], send)


def _drive_exchanges(
    base_url: str,
    exchanges: Sequence[Exchange],
    send: Send | None = None,
) -> None:
    sender = send or request
    for exchange in exchanges:
        status, response = sender(
            exchange.method,
            f"{base_url}{exchange.path}",
            exchange.body,
        )
        print(f"{exchange.method} {exchange.path} -> {status} {response[:60]}")
        verify(exchange, status, response)


async def drive_async(base_url: str, send: AsyncSend) -> None:
    """Asynchronously send and verify every measured request."""
    for exchange in _action_table()[1:]:
        status, response = await send(
            exchange.method,
            f"{base_url}{exchange.path}",
            exchange.body,
        )
        print(f"{exchange.method} {exchange.path} -> {status} {response[:60]}")
        verify(exchange, status, response)


async def drive_selected_async(base_url: str, send: AsyncSend) -> None:
    """Asynchronously send the runner-selected request."""
    exchange = scenario_request()
    status, response = await send(
        exchange.method,
        f"{base_url}{exchange.path}",
        exchange.body,
    )
    print(f"{exchange.method} {exchange.path} -> {status} {response[:60]}")


def verify(exchange: Exchange, status: int, response: str) -> None:
    """Check one answer against the exchange that describes it.

    A server scenario declares routes in the framework under test, which is
    the point — an instrumentation reads the route from that declaration.
    Its answers stay common: a server returning different statuses or bodies
    would otherwise silently make its coverage file incomparable.
    """
    expected_body = exchange.response_body.replace(
        "${requestBody}", exchange.body or "{}"
    )

    if status != exchange.status:
        raise ContractError(
            f"{exchange.method} {exchange.path} answered {status}, but the "
            f"contract's request answers {exchange.status}"
        )

    # Parsed, not compared as text: whitespace and key order are a language's
    # choice of JSON writer, and neither is part of the contract.
    try:
        got, want = json.loads(response), json.loads(expected_body)
    except json.JSONDecodeError as error:
        raise ContractError(
            f"{exchange.method} {exchange.path} answered {response[:200]!r}, "
            "which is not the JSON the contract's request describes"
        ) from error
    if _canonical_json(got) != _canonical_json(want):
        raise ContractError(
            f"{exchange.method} {exchange.path} answered {got!r}, but the "
            f"contract's request answers {want!r}"
        )


def wait_for_port(
    port: int, *, host: str = "127.0.0.1", timeout: float = 30.0
) -> bool:
    """Wait for something to accept connections on ``port``.

    Readiness in two steps, and this is the first: a bare connect makes no
    request, so it cannot leave a span behind however many times it is tried
    while a server starts up.
    """
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            with socket.create_connection((host, port), timeout=remaining):
                return True
        except OSError:
            time.sleep(
                min(_HEALTH_POLL_SECONDS, max(0, deadline - time.monotonic()))
            )
    return False


def wait_for_health(base_url: str, timeout: float = 30.0) -> None:
    """Ask once whether the app is ready, waiting up to ``timeout``.

    The second step of readiness, and the first request the app sees. Each
    server scenario request becomes telemetry, so a failed readiness exchange
    is reported rather than retried and recorded again.
    """
    _wait_for_health_exchange(base_url, _action_table()[0], timeout)


def _wait_for_health_exchange(
    base_url: str, readiness: Exchange, timeout: float = 30.0
) -> None:
    with urllib.request.urlopen(  # noqa: S310
        urllib.request.Request(  # noqa: S310
            f"{base_url}{readiness.path}",
            headers=client_headers(None),
        ),
        timeout=timeout,
    ):
        return


def request(
    method: str,
    url: str,
    body: str | None = None,
) -> tuple[int, str]:
    """Send one request, reading an error response as a result like any other.

    A 404 or 500 is what the scenario asked for, so it comes back as a status
    rather than an exception.
    """
    prepared = urllib.request.Request(  # noqa: S310
        url,
        data=None if body is None else body.encode("utf-8"),
        method=method,
        headers=client_headers(body),
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            prepared, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def serve(
    app_factory: Callable[[], object], *, host: str = "127.0.0.1"
) -> None:
    """Serve a WSGI app until the driver closes standard input.

    What every server scenario does, in the one language these tools are
    written in: bind the port the driver chose, answer the exchanges, and
    shut down on EOF so the SDK flushes before the process exits.

    ``app_factory`` is a zero-argument callable rather than an app so the SDK
    is fully installed before the instrumented framework constructs anything.
    """
    app = app_factory()
    with make_server(
        host,
        scenario_port(),
        app,  # pyright: ignore[reportArgumentType]
        handler_class=_QuietHandler,
    ) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            wait_for_eof()
        finally:
            httpd.shutdown()
            thread.join(timeout=REQUEST_TIMEOUT_SECONDS)


def scenario_port() -> int:
    """The port the driver told this scenario to listen on."""
    raw = os.environ.get(PORT_VARIABLE)
    if not raw:
        raise RuntimeError(
            f"{PORT_VARIABLE} is not set — a server scenario is started by "
            "`otel-http-drive`, which chooses the port"
        )
    return int(raw)


def wait_for_eof() -> None:
    """Block until standard input closes, which is how the driver says stop.

    A closed pipe rather than a signal: it means the same thing on every
    platform, and it needs no extra route, which would show up as coverage the
    scenario never meant to record.
    """
    while sys.stdin.buffer.read(1):
        pass


def reserve_port(host: str = "127.0.0.1") -> tuple[int, socket.socket]:
    """Take a free port and return the socket currently holding it.

    Keep the socket open until immediately before the server starts to narrow
    the window in which a parallel run can take the port. The server must bind
    the port itself, so closing the reservation still leaves a small race.
    """
    reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reservation.bind((host, 0))
    return int(reservation.getsockname()[1]), reservation


class _QuietHandler(WSGIRequestHandler):
    """The default handler logs every request to stderr; the driver already
    prints what it sent.
    """

    def get_environ(self):
        """The environ, plus the two keys a real WSGI server also supplies.

        ``wsgiref.simple_server`` is PEP 3333 and no more, but a WSGI
        instrumentation reads ``url.path`` and ``url.query`` from ``RAW_URI``
        and ``client.port`` from ``REMOTE_PORT`` — neither of which PEP 3333
        defines, and both of which gunicorn, uWSGI and Werkzeug set. Without
        them the harness, not the instrumentation, would be the reason those
        attributes are missing from a coverage file.
        """
        environ = super().get_environ()
        # The raw request target, before wsgiref splits and unquotes it.
        environ["RAW_URI"] = self.path
        environ["REMOTE_PORT"] = str(self.client_address[1])
        return environ

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        del format, args
