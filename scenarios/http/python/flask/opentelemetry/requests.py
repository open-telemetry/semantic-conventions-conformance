# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a Flask HTTP server under a standard request load.

The routes are the only thing here — the requests come from
``otel_http_test_client``, whose docstring is the contract they implement.
"""

from otel_http_test_client import serve_and_drive


def create_app():
    from flask import Flask, jsonify, request

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify(ok=True)

    @app.get("/users/<user_id>")
    def get_user(user_id):
        return jsonify(id=int(user_id), name="Alice")

    @app.post("/items")
    def create_item():
        return jsonify(created=True, payload=request.get_json(silent=True) or {}), 201

    @app.get("/status/<int:code>")
    def get_status(code):
        return jsonify(message={404: "not found", 500: "server error"}.get(code, "ok")), code

    return app


serve_and_drive(create_app)
