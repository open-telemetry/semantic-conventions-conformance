# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The requests every HTTP conformance scenario makes.

Coverage files are only comparable if every scenario is exercised the same
way, so the request sequence lives here once rather than in each scenario.
Both sides of the domain use it:

- A **server** scenario is its own server. ``serve_and_drive`` brings the app
  up and sends :data:`REQUESTS` at it with the standard library, which is
  never the thing under test.
- A **client** scenario is the sender. It passes its own library as ``send``
  to :func:`drive`, pointed at a server the runner started — see
  ``tools/http/mock-server``, which answers the same routes.

**The route contract.** A scenario's app implements exactly these:

===========================  ======  ======================================
route                        method  responds
===========================  ======  ======================================
``/health``                  GET     200
``/users/<user_id>``         GET     200 JSON
``/items``                   POST    201 JSON, echoing the body
``/status/<code>``           GET     that status
===========================  ======  ======================================

This package itself is standard library only. A third-party client here would
be picked up by an HTTP client instrumentation the moment one is installed
alongside, and its spans would land in the report as if the scenario had meant
to produce them — which is exactly what a client scenario passes ``send`` for.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Sequence
from wsgiref.simple_server import WSGIRequestHandler, make_server

__all__ = [
    "REQUESTS",
    "Request",
    "Send",
    "drive",
    "request",
    "serve_and_drive",
    "wait_for_health",
]

Request = tuple[str, str, "str | None"]
# How one request is sent: method, absolute URL, body → status, response body.
# A client scenario supplies its own so its library is the one instrumented.
Send = Callable[[str, str, "str | None"], "tuple[int, str]"]

# What every HTTP server scenario sends. Each one is here for an attribute it
# makes the instrumentation set, so the coverage files say something.
REQUESTS: Sequence[Request] = (
    # A templated route: `http.route` should be the template, not the path,
    # and the span name should be built from it.
    ("GET", "/users/123", None),
    # A query string, which is its own attribute (`url.query`) and must not
    # leak into `http.route`, `url.path` or the span name.
    ("GET", "/users/123?fields=name&verbose=true", None),
    # A non-GET carrying a body.
    ("POST", "/items", json.dumps({"name": "widget"})),
    # Both error classes: `error.type` and a 4xx/5xx `http.response.status_code`,
    # on the span and on the duration metric.
    ("GET", "/status/404", None),
    ("GET", "/status/500", None),
)

_HEALTH_POLL_SECONDS = 0.05
_REQUEST_TIMEOUT_SECONDS = 10


class _QuietHandler(WSGIRequestHandler):
    """The default handler logs every request to stderr; the driver already does."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        del format, args


def serve_and_drive(
    app_factory: Callable[[], object], *, host: str = "127.0.0.1"
) -> None:
    """Serve a WSGI app on a free port, drive it, and stop.

    ``app_factory`` is a zero-argument callable rather than an app so the SDK
    is fully installed before the instrumented framework constructs anything.

    Port 0: the OS picks a free one, so parallel runs of different scenarios
    can't collide on a hard-coded port.
    """
    with make_server(host, 0, app_factory(), handler_class=_QuietHandler) as httpd:  # pyright: ignore[reportArgumentType]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            drive(f"http://{host}:{httpd.server_port}")
        finally:
            httpd.shutdown()
            thread.join(timeout=_REQUEST_TIMEOUT_SECONDS)


def drive(base_url: str, send: Send | None = None) -> None:
    """Wait for the server, then send :data:`REQUESTS` in order.

    ``send`` defaults to the standard library. A client scenario passes its
    own library instead — that call is the thing being measured.
    """
    sender = send or request
    wait_for_health(base_url)
    for method, path, body in REQUESTS:
        status, response = sender(method, f"{base_url}{path}", body)
        print(f"{method} {path} -> {status} {response[:60]}")


def wait_for_health(base_url: str, timeout: float = 10.0) -> None:
    """Block until the app answers ``/health``, or give up saying so."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"{base_url}/health", timeout=1
            ):
                return
        except (OSError, http.client.HTTPException):
            # Still starting: connection refused, reset, or a truncated
            # response are all expected until it is listening.
            time.sleep(_HEALTH_POLL_SECONDS)
    raise RuntimeError(
        f"the scenario's server did not answer {base_url}/health within "
        f"{timeout}s"
    )


def request(method: str, url: str, body: str | None = None) -> tuple[int, str]:
    """Send one request, reading an error response as a result like any other.

    A 404 or 500 is what the scenario asked for, so it comes back as a status
    rather than an exception.
    """
    headers = {"Content-Type": "application/json"} if body is not None else {}
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
