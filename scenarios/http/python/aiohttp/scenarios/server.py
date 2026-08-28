# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The aiohttp server workload, with no instrumentation attached."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from aiohttp import web

from otel_http_test_client import (
    CONTENT_TYPE,
    respond,
    scenario_port,
    wait_for_eof,
)


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", _answer)
    app.router.add_get("/users/{user_id}", _answer)
    app.router.add_post("/items", _answer)
    app.router.add_get("/status/{code}", _answer)
    return app


async def _answer(request: web.Request) -> web.Response:
    body = await request.text() or None
    status, payload = respond(request.method, request.path, body)
    return web.Response(text=payload, status=status, content_type=CONTENT_TYPE)


def serve(app_factory: Callable[[], web.Application]) -> None:
    asyncio.run(_serve(app_factory()))


async def _serve(app: web.Application) -> None:
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", scenario_port())
    await site.start()
    try:
        await asyncio.to_thread(wait_for_eof)
    finally:
        await runner.cleanup()
