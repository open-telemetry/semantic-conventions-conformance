# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Django workload, with no instrumentation attached."""

from __future__ import annotations

import django
from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.core.wsgi import get_wsgi_application
from django.http import HttpRequest, HttpResponse
from django.urls import path

from otel_http_test_client import CONTENT_TYPE, respond

if not settings.configured:
    settings.configure(
        ALLOWED_HOSTS=["127.0.0.1"],
        DEBUG=False,
        MIDDLEWARE=[],
        ROOT_URLCONF=__name__,
        SECRET_KEY="conformance",
    )
    django.setup()


def _answer(request: HttpRequest, **parameters: str) -> HttpResponse:
    del parameters
    body = request.body.decode() or None
    status, payload = respond(request.method, request.path, body)
    return HttpResponse(payload, status=status, content_type=CONTENT_TYPE)


urlpatterns = [
    path("health", _answer),
    path("users/<str:user_id>", _answer),
    path("items", _answer),
    path("status/<str:code>", _answer),
]


def create_app() -> WSGIHandler:
    return get_wsgi_application()
