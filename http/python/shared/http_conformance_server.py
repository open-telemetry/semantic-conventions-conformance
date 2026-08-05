# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Minimal HTTP server for conformance scenarios.

Provides a few endpoints that return predictable responses so the
instrumented HTTP client generates spans with known attributes.
"""

import argparse
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class TestHandler(BaseHTTPRequestHandler):
    """Simple handler that responds to a few routes."""

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, "ok")
        elif self.path == "/users/123":
            self._respond(200, '{"id": 123, "name": "Alice"}')
        elif self.path == "/status/404":
            self._respond(404, "not found")
        elif self.path == "/status/500":
            self._respond(500, "internal server error")
        else:
            self._respond(200, '{"message": "hello"}')

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            # Drain the request body so the connection stays usable.
            self.rfile.read(content_length)
        self._respond(201, '{"created": true}')

    def _respond(self, code, body):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, format, *args):
        # Suppress request logging to keep test output clean.
        pass


def start_server(host="127.0.0.1", port=8090):
    """Start the test HTTP server and return (server, thread)."""
    server = HTTPServer((host, port), TestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    server, thread = start_server(args.host, args.port)
    print(f"HTTP test server listening on {args.host}:{args.port}")
    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
