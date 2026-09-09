# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The server an HTTP *client* conformance scenario calls.

A server scenario is its own server. A client scenario needs one to call, and
it has to answer the same exchanges the server scenarios do — otherwise
the two sides of the domain are measured against different traffic. So the
contract lives once, in ``otel_http_test_client``, and this serves it through
that package's :func:`~otel_http_test_client.respond`, not a second copy here.

Standard library only, and deliberately uninstrumented: it runs as a separate
process the runner starts, and nothing it emits should reach the report.
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from otel_http_test_client import CONTENT_TYPE, respond


class _Handler(BaseHTTPRequestHandler):
    # HTTP/1.1 so a client can keep the connection alive, which is what an
    # instrumented client library does by default.
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802  (BaseHTTPRequestHandler's API)
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._handle("POST")

    def _handle(self, method: str) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else None
        # Strict about the request body, which a server scenario's own answers
        # are not. Answering 400 identifies a client that omitted or changed the
        # contract's body before response validation sees only the echoed value.
        status, payload = respond(
            method,
            urlparse(self.path).path,
            body,
            check_request_body=True,
        )
        encoded = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", CONTENT_TYPE)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        """Quiet: the runner captures this process's output only on failure."""


def main() -> None:
    parser = argparse.ArgumentParser(prog="http-mock-server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    arguments = parser.parse_args()
    ThreadingHTTPServer(
        (arguments.host, arguments.port), _Handler
    ).serve_forever()


if __name__ == "__main__":
    main()
