# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Tornado workload, with no instrumentation attached."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import tornado.web

from otel_http_test_client import (
    CONTENT_TYPE,
    respond,
    scenario_port,
    wait_for_eof,
)


class BaseHandler(tornado.web.RequestHandler):
    def _answer(self) -> None:
        body = self.request.body.decode() or None
        status, payload = respond(self.request.method, self.request.path, body)
        self.set_status(status)
        self.set_header("Content-Type", CONTENT_TYPE)
        self.finish(payload)


class HealthHandler(BaseHandler):
    def get(self) -> None:
        self._answer()


class UserHandler(BaseHandler):
    def get(self, user_id: str) -> None:
        del user_id
        self._answer()


class ItemsHandler(BaseHandler):
    def post(self) -> None:
        self._answer()


class StatusHandler(BaseHandler):
    def get(self, code: str) -> None:
        del code
        self._answer()


def create_app() -> tornado.web.Application:
    return tornado.web.Application(
        [
            (r"/health", HealthHandler),
            (r"/users/([^/]+)", UserHandler),
            (r"/items", ItemsHandler),
            (r"/status/([^/]+)", StatusHandler),
        ]
    )


def serve(
    app_factory: Callable[[], tornado.web.Application],
) -> None:
    asyncio.run(_serve(app_factory()))


async def _serve(app: tornado.web.Application) -> None:
    server = app.listen(scenario_port(), address="127.0.0.1")
    try:
        await asyncio.to_thread(wait_for_eof)
    finally:
        server.stop()
        await server.close_all_connections()
