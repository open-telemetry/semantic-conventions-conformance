# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The HTTPX workload, with no instrumentation attached."""

from __future__ import annotations

import httpx

from otel_http_test_client import (
    REQUEST_TIMEOUT_SECONDS,
    client_headers,
    drive,
    mock_server_url,
)


def run() -> None:
    with httpx.Client(
        timeout=REQUEST_TIMEOUT_SECONDS,
        trust_env=False,
    ) as client:

        def send(method: str, url: str, body: str | None) -> tuple[int, str]:
            response = client.request(
                method,
                url,
                content=body,
                headers=client_headers(body),
            )
            return response.status_code, response.text

        drive(mock_server_url(), send)
