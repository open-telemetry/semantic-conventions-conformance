# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Falcon workload, with no instrumentation attached."""

from __future__ import annotations

import falcon

from otel_http_test_client import CONTENT_TYPE, respond


class Resource:
    def on_get(
        self, request: falcon.Request, response: falcon.Response, **params: str
    ) -> None:
        del params
        self._answer(request, response)

    def on_post(
        self, request: falcon.Request, response: falcon.Response, **params: str
    ) -> None:
        del params
        self._answer(request, response)

    @staticmethod
    def _answer(request: falcon.Request, response: falcon.Response) -> None:
        body = request.bounded_stream.read().decode() or None
        status, payload = respond(request.method, request.path, body)
        response.status = falcon.code_to_http_status(status)
        response.content_type = CONTENT_TYPE
        response.text = payload


def create_app() -> falcon.App:
    app = falcon.App()
    resource = Resource()
    app.add_route("/health", resource)
    app.add_route("/users/{user_id}", resource)
    app.add_route("/items", resource)
    app.add_route("/status/{code}", resource)
    return app
