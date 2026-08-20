# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Flask application every Flask instrumentation here serves.

Shared by every implementation under ``flask/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

The routes are declared with Flask's own decorators because that declaration
is what an instrumentation reads ``http.route`` from — the one part of a
server scenario no two frameworks can share. Answering them is an exact lookup
of the concrete request, so it goes through the contract's
:func:`~otel_http_test_client.respond` rather than a second copy of the
statuses and bodies.
"""

from __future__ import annotations

from flask import Flask, Response, request

from otel_http_test_client import CONTENT_TYPE, respond


def create_app() -> Flask:
    """Build the app, with nothing attached to it.

    A function rather than a module-level app, so the caller decides when it
    is constructed: an instrumentation that wraps an app has to be installed
    with the SDK already in place.
    """
    app = Flask(__name__)

    # The path parameters go unread: the template they make Flask record is
    # what is being measured, and the answer is an exact lookup of the
    # concrete request.
    @app.get("/health")
    def health() -> Response:
        return _answer()

    @app.get("/users/<user_id>")
    def user(user_id: str) -> Response:
        return _answer()

    @app.post("/items")
    def items() -> Response:
        return _answer()

    @app.get("/status/<code>")
    def status(code: str) -> Response:
        return _answer()

    return app


def _answer() -> Response:
    body = request.get_data(as_text=True) or None
    status, payload = respond(request.method, request.path, body)
    return Response(payload, status=status, content_type=CONTENT_TYPE)
