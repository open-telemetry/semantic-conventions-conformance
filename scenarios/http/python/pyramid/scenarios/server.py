# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Pyramid workload, with no instrumentation attached."""

from __future__ import annotations

from pyramid.config import Configurator
from pyramid.request import Request
from pyramid.response import Response

from otel_http_test_client import CONTENT_TYPE, respond


def answer(request: Request) -> Response:
    body = request.body.decode() or None
    status, payload = respond(request.method, request.path, body)
    return Response(
        text=payload, status=status, content_type=CONTENT_TYPE
    )


def create_config() -> Configurator:
    config = Configurator()
    config.add_route("health", "/health")
    config.add_route("user", "/users/{user_id}")
    config.add_route("items", "/items")
    config.add_route("status", "/status/{code}")
    config.add_view(answer, route_name="health", request_method="GET")
    config.add_view(answer, route_name="user", request_method="GET")
    config.add_view(answer, route_name="items", request_method="POST")
    config.add_view(answer, route_name="status", request_method="GET")
    return config
