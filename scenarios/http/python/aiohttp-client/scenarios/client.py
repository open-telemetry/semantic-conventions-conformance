# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The aiohttp client workload, with no instrumentation attached."""

from __future__ import annotations

import asyncio
import os

import aiohttp

from otel_http_test_client import (
    CONTENT_TYPE,
    USER_AGENT,
    drive_async,
)

_REQUEST_TIMEOUT_SECONDS = 10


def run() -> None:
    asyncio.run(_run())


async def _run() -> None:
    base_url = os.environ.get("MOCK_SERVER_URL")
    if not base_url:
        raise RuntimeError("MOCK_SERVER_URL is not set")

    async with aiohttp.ClientSession(
        headers={"User-Agent": USER_AGENT},
        timeout=aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT_SECONDS),
        trust_env=False,
    ) as session:

        async def send(
            method: str, url: str, body: str | None
        ) -> tuple[int, str]:
            headers = (
                {"Content-Type": CONTENT_TYPE} if body is not None else {}
            )
            async with session.request(
                method, url, data=body, headers=headers
            ) as response:
                return response.status, await response.text()

        await drive_async(base_url, send)
