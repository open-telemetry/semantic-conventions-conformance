# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The urllib3 workload, with no instrumentation attached."""

from __future__ import annotations

import os

import urllib3

from otel_http_test_client import CONTENT_TYPE, USER_AGENT, drive

_REQUEST_TIMEOUT_SECONDS = 10


def run() -> None:
    base_url = os.environ.get("MOCK_SERVER_URL")
    if not base_url:
        raise RuntimeError("MOCK_SERVER_URL is not set")

    with urllib3.PoolManager(
        headers={"User-Agent": USER_AGENT},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    ) as pool:

        def send(method: str, url: str, body: str | None) -> tuple[int, str]:
            headers = (
                {"Content-Type": CONTENT_TYPE} if body is not None else {}
            )
            response = pool.request(
                method,
                url,
                body=None if body is None else body.encode(),
                headers=headers,
            )
            return response.status, response.data.decode()

        drive(base_url, send)
