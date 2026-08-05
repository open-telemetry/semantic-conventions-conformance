# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: OTel contrib opentelemetry-instrumentation-flask (HTTP server)."""

from scenario_harness import serve_via_wsgiref

TEST_SERVER_PORT = 8091


def create_app():
    from flask import Flask, jsonify, request
    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify(ok=True)

    @app.get("/users/<user_id>")
    def get_user(user_id):
        return jsonify(id=int(user_id), name="Alice")

    @app.post("/items")
    def create_item():
        payload = request.get_json(silent=True) or {}
        return jsonify(created=True, payload=payload), 201

    @app.get("/status/<int:code>")
    def get_status(code):
        body = {404: "not found", 500: "internal server error"}.get(code, "ok")
        return jsonify(message=body), code

    FlaskInstrumentor().instrument_app(app)
    return app


def main():
    serve_via_wsgiref(
        create_app,
        TEST_SERVER_PORT,
    )


if __name__ == "__main__":
    main()
