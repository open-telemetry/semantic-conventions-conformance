# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The urllib workload, with no instrumentation attached."""

from __future__ import annotations

import os
import urllib.error
import urllib.request

from otel_http_test_client import CONTENT_TYPE, USER_AGENT, drive

_REQUEST_TIMEOUT_SECONDS = 10


def run() -> None:
    base_url = os.environ.get("MOCK_SERVER_URL")
    if not base_url:
        raise RuntimeError("MOCK_SERVER_URL is not set")

    def send(method: str, url: str, body: str | None) -> tuple[int, str]:
        headers = {"User-Agent": USER_AGENT}
        if body is not None:
            headers["Content-Type"] = CONTENT_TYPE
        request = urllib.request.Request(  # noqa: S310
            url,
            data=None if body is None else body.encode(),
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(  # noqa: S310
                request, timeout=_REQUEST_TIMEOUT_SECONDS
            ) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    drive(base_url, send)
