# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Runs an ASGI application until the HTTP driver closes standard input."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import uvicorn

from otel_http_test_client import scenario_port, wait_for_eof


def serve(app_factory: Callable[[], object]) -> None:
    """Serve a freshly constructed ASGI app on the driver-selected port."""
    asyncio.run(_serve(app_factory()))


async def _serve(app: object) -> None:
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=scenario_port(),
            log_level="warning",
            lifespan="off",
        )
    )
    task = asyncio.create_task(server.serve())
    try:
        await asyncio.to_thread(wait_for_eof)
    finally:
        server.should_exit = True
        await task
