# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The urllib3 workload, with no instrumentation attached."""

from __future__ import annotations

import urllib3

from otel_http_test_client import (
    REQUEST_TIMEOUT_SECONDS,
    client_headers,
    drive,
    mock_server_url,
)


def run() -> None:
    with urllib3.PoolManager(timeout=REQUEST_TIMEOUT_SECONDS) as pool:

        def send(method: str, url: str, body: str | None) -> tuple[int, str]:
            # urllib3 falls back to the pool's own headers only when this
            # argument is None, so every header the request needs has to be
            # named here.
            response = pool.request(
                method,
                url,
                body=None if body is None else body.encode(),
                headers=client_headers(body),
            )
            return response.status, response.data.decode()

        drive(mock_server_url(), send)
