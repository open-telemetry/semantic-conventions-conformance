# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The server an HTTP *client* conformance scenario calls.

A server scenario is its own server. A client scenario needs one to call, and
it has to answer the same routes the server scenarios implement — otherwise
the two sides of the domain are measured against different traffic. So the
contract lives once, in ``otel_http_test_client``, and this serves it.

Standard library only, and deliberately uninstrumented: it runs as a separate
process the runner starts, and nothing it emits should reach the report.
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# Digits only: the id is echoed back as a number, and anything else
# should read as an unknown route rather than fail the handler.
_USER = re.compile(r"^/users/(?P<user_id>[0-9]+)$")
_STATUS = re.compile(r"^/status/(?P<code>\d+)$")


def _respond(path: str, method: str, body: bytes) -> tuple[int, object]:
    """The route contract, as one function. See ``otel_http_test_client``."""
    if path == "/health" and method == "GET":
        return 200, {"ok": True}
    if (user := _USER.match(path)) and method == "GET":
        return 200, {"id": int(user["user_id"]), "name": "Alice"}
    if path == "/items" and method == "POST":
        return 201, {"created": True, "payload": json.loads(body or b"{}")}
    if status := _STATUS.match(path):
        code = int(status["code"])
        message = {404: "not found", 500: "server error"}.get(code, "ok")
        return code, {"message": message}
    return 404, {"message": "not found"}


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
        body = self.rfile.read(length) if length else b""
        status, payload = _respond(urlparse(self.path).path, method, body)
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
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
