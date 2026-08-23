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

    with urllib3.PoolManager(timeout=_REQUEST_TIMEOUT_SECONDS) as pool:

        def send(method: str, url: str, body: str | None) -> tuple[int, str]:
            # urllib3 falls back to the pool's own headers only when this
            # argument is None, so every header the request needs has to be
            # named here.
            headers = {"User-Agent": USER_AGENT}
            if body is not None:
                headers["Content-Type"] = CONTENT_TYPE
            response = pool.request(
                method,
                url,
                body=None if body is None else body.encode(),
                headers=headers,
            )
            return response.status, response.data.decode()

        drive(base_url, send)
