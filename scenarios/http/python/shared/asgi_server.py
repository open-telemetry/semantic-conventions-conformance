# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Runs an ASGI application until the HTTP driver closes standard input."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
from collections.abc import Callable

import uvicorn

from otel_http_test_client import scenario_port


def serve(app_factory: Callable[[], object]) -> None:
    """Serve a freshly constructed ASGI app on the driver-selected port."""
    asyncio.run(_serve(app_factory()))


async def _wait_for_eof() -> None:
    loop = asyncio.get_running_loop()
    done: asyncio.Future[None] = loop.create_future()
    stdin = sys.stdin.fileno()

    def finish() -> None:
        if not done.done():
            done.set_result(None)

    def on_readable() -> None:
        if not os.read(stdin, 4096):
            loop.remove_reader(stdin)
            finish()

    try:
        loop.add_reader(stdin, on_readable)
    except NotImplementedError:
        # Proactor loops cannot watch stdin. An unbuffered daemon reader can
        # be abandoned safely if uvicorn exits before the driver closes stdin.
        def wait() -> None:
            try:
                while os.read(stdin, 4096):
                    pass
            except OSError:
                pass
            finally:
                loop.call_soon_threadsafe(finish)

        threading.Thread(target=wait, daemon=True).start()
    else:
        try:
            await done
        finally:
            loop.remove_reader(stdin)
        return

    await done


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
    serve_task = asyncio.create_task(server.serve())
    eof_task = asyncio.create_task(_wait_for_eof())
    try:
        done, _ = await asyncio.wait(
            (serve_task, eof_task),
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
    finally:
        eof_task.cancel()
        server.should_exit = True
        await asyncio.gather(serve_task, return_exceptions=True)
