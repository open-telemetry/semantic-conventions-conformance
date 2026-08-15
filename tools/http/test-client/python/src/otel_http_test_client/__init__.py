# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The HTTP conformance exchanges a server answers or a client sends.

Coverage files are only comparable if every scenario is exercised the same
way, so both halves live in ``contract.json`` once rather than in each
language. Both sides of the domain use it:

- A **server** scenario is a plain server process. It declares matching routes
    with the framework under test, listens on the port in
    ``OTEL_HTTP_SCENARIO_PORT``, and stays up until its standard input closes;
    ``otel-http-drive`` starts it, sends :data:`REQUESTS` at it from outside,
    then closes standard input so it flushes and exits.
- A **client** scenario is the sender. It passes its own library as ``send``
  to :func:`drive`, pointed at a server the runner started — see
  ``tools/http/mock-server``, which answers :data:`EXCHANGES` from this module.

Nothing under test ever drives a server scenario: the driver is a separate
process, so no instrumentation loaded into the scenario can pick the driver up
and record client spans the scenario never meant to produce.

:func:`drive` checks every response against its exchange. A server scenario
declares routes in its framework's native form — that declaration is what an
instrumentation reads a route from — but every status and body is a constant
from the shared file because the requests are fixed.

This package is standard library only, so installing it next to a scenario
drags no dependency into a run.
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
from pathlib import Path
from typing import Callable, NamedTuple, Sequence
from wsgiref.simple_server import WSGIRequestHandler, make_server

__all__ = [
    "CONTENT_TYPE",
    "CONTRACT",
    "EXCHANGES",
    "PORT_VARIABLE",
    "REQUESTS",
    "USER_AGENT",
    "ContractError",
    "Exchange",
    "Send",
    "drive",
    "request",
    "reserve_port",
    "respond",
    "scenario_port",
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
    # What the request is in the sequence for — the attribute it should make
    # an instrumentation record. Carried as data rather than as a comment so
    # every language reading the contract has it too.
    why: str


# How one request is sent: method, absolute URL, body → status, response body.
# A client scenario supplies its own so its library is the one instrumented.
Send = Callable[[str, str, "str | None"], "tuple[int, str]"]

# The port a server scenario listens on. ``otel-http-drive`` chooses it, which
# is what lets different scenarios run in parallel without colliding.
PORT_VARIABLE = "OTEL_HTTP_SCENARIO_PORT"

# Fixed rather than the interpreter's default, so a server scenario is driven
# by the same client whichever Python happens to be installed.
USER_AGENT = "otel-http-conformance/1"

_HEALTH_POLL_SECONDS = 0.05
_REQUEST_TIMEOUT_SECONDS = 10


def _contract() -> Path:
    """Where ``contract.json`` is.

    Installed beside this module, or — in a checkout — above the Python
    package, since the contract belongs to every language rather than to this
    one.
    """
    packaged = Path(__file__).parent / "contract.json"
    if packaged.is_file():
        return packaged
    return Path(__file__).resolve().parents[3] / "contract.json"


CONTRACT = _contract()

_DOCUMENT = json.loads(CONTRACT.read_text(encoding="utf-8"))

EXCHANGES: Sequence[Exchange] = tuple(
    Exchange(
        method=entry["method"],
        path=entry["path"],
        body=entry.get("body"),
        status=entry["status"],
        response_body=entry["responseBody"],
        readiness=entry.get("readiness", False),
        why=entry["why"],
    )
    for entry in _DOCUMENT["requests"]
)

REQUESTS: Sequence[Exchange] = tuple(
    exchange for exchange in EXCHANGES if not exchange.readiness
)
_READINESS = next(exchange for exchange in EXCHANGES if exchange.readiness)

# Every route answers JSON, so a scenario that reads the contract has one
# content type to send rather than a rule per route.
CONTENT_TYPE = "application/json"


def _exchange_for(method: str, path: str) -> Exchange | None:
    """The concrete exchange answering ``method path``, if there is one."""
    path = path.split("?", 1)[0]
    for exchange in EXCHANGES:
        if (
            exchange.method == method
            and exchange.path.split("?", 1)[0] == path
        ):
            return exchange
    return None


def respond(
    method: str, path: str, body: str | None = None
) -> tuple[int, str]:
    """What the contract answers to one request.

    The whole answer contract in one function, so the mock server a client
    scenario calls and any Python server scenario answer identically.
    """
    exchange = _exchange_for(method, path)
    if exchange is None:
        return 404, '{"message": "no such route"}'
    return exchange.status, exchange.response_body.replace(
        "${requestBody}", body or "{}"
    )


def drive(base_url: str, send: Send | None = None) -> None:
    """Send :data:`REQUESTS` at ``base_url`` in order, checking each answer.

    ``send`` defaults to the standard library. A client scenario passes its
    own library instead — that call is the thing being measured.

    The server is assumed to be up: waiting is :func:`wait_for_health`, kept
    separate because every extra request a driver makes while a server starts
    is a span in that server's report.
    """
    sender = send or request
    for exchange in REQUESTS:
        status, response = sender(
            exchange.method,
            f"{base_url}{exchange.path}",
            exchange.body,
        )
        print(f"{exchange.method} {exchange.path} -> {status} {response[:60]}")
        verify(exchange, status, response)


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
    if got != want:
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
    with urllib.request.urlopen(  # noqa: S310
        urllib.request.Request(  # noqa: S310
            f"{base_url}{_READINESS.path}",
            headers={"User-Agent": USER_AGENT},
        ),
        timeout=timeout,
    ):
        return


def request(method: str, url: str, body: str | None = None) -> tuple[int, str]:
    """Send one request, reading an error response as a result like any other.

    A 404 or 500 is what the scenario asked for, so it comes back as a status
    rather than an exception.
    """
    headers = {"User-Agent": USER_AGENT}
    if body is not None:
        headers["Content-Type"] = "application/json"
    prepared = urllib.request.Request(  # noqa: S310
        url,
        data=None if body is None else body.encode("utf-8"),
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(  # noqa: S310
            prepared, timeout=_REQUEST_TIMEOUT_SECONDS
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
            thread.join(timeout=_REQUEST_TIMEOUT_SECONDS)


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

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        del format, args
