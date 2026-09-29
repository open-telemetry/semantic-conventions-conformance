# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Starlette workload, with no instrumentation attached."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from otel_http_test_client import CONTENT_TYPE, respond


async def answer(request: Request) -> Response:
    body = (await request.body()).decode() or None
    status, payload = respond(request.method, request.url.path, body)
    return Response(payload, status_code=status, media_type=CONTENT_TYPE)


def create_app() -> Starlette:
    return Starlette(
        routes=[
            Route("/health", answer, methods=["GET"]),
            Route("/users/{user_id}", answer, methods=["GET"]),
            Route("/items", answer, methods=["POST"]),
            Route("/status/{code}", answer, methods=["GET"]),
        ]
    )
