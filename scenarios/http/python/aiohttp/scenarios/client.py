# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The aiohttp client workload, with no instrumentation attached."""

from __future__ import annotations

import asyncio

import aiohttp

from otel_http_test_client import (
    REQUEST_TIMEOUT_SECONDS,
    client_headers,
    drive_selected_async,
    mock_server_url,
)


def run() -> None:
    asyncio.run(_run())


async def _run() -> None:
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
        trust_env=False,
    ) as session:

        async def send(
            method: str, url: str, body: str | None
        ) -> tuple[int, str]:
            async with session.request(
                method, url, data=body, headers=client_headers(body)
            ) as response:
                return response.status, await response.text()

        await drive_selected_async(mock_server_url(), send)
