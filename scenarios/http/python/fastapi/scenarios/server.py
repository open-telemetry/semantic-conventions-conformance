# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The FastAPI workload, with no instrumentation attached."""

from __future__ import annotations

from fastapi import FastAPI, Request, Response

from otel_http_test_client import CONTENT_TYPE, respond


def create_app() -> FastAPI:
    app = FastAPI()

    async def answer(request: Request) -> Response:
        body = (await request.body()).decode() or None
        status, payload = respond(request.method, request.url.path, body)
        return Response(payload, status_code=status, media_type=CONTENT_TYPE)

    app.add_api_route("/health", answer, methods=["GET"])
    app.add_api_route("/users/{user_id}", answer, methods=["GET"])
    app.add_api_route("/items", answer, methods=["POST"])
    app.add_api_route("/status/{code}", answer, methods=["GET"])
    return app
