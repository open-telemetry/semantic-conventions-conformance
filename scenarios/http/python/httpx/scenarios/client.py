# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The HTTPX workload, with no instrumentation attached."""

from __future__ import annotations

import os

import httpx

from otel_http_test_client import CONTENT_TYPE, USER_AGENT, drive

_REQUEST_TIMEOUT_SECONDS = 10


def run() -> None:
    base_url = os.environ.get("MOCK_SERVER_URL")
    if not base_url:
        raise RuntimeError("MOCK_SERVER_URL is not set")

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=_REQUEST_TIMEOUT_SECONDS,
        trust_env=False,
    ) as client:

        def send(method: str, url: str, body: str | None) -> tuple[int, str]:
            headers = (
                {"Content-Type": CONTENT_TYPE} if body is not None else {}
            )
            response = client.request(
                method, url, content=body, headers=headers
            )
            return response.status_code, response.text

        drive(base_url, send)
