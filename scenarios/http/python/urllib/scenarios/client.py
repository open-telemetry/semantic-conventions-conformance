# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The urllib workload, with no instrumentation attached."""

from __future__ import annotations

import urllib.error
import urllib.request

from otel_http_test_client import (
    REQUEST_TIMEOUT_SECONDS,
    client_headers,
    drive,
    mock_server_url,
)


def run() -> None:
    def send(method: str, url: str, body: str | None) -> tuple[int, str]:
        request = urllib.request.Request(  # noqa: S310
            url,
            data=None if body is None else body.encode(),
            method=method,
            headers=client_headers(body),
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=REQUEST_TIMEOUT_SECONDS
            ) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    drive(mock_server_url(), send)
