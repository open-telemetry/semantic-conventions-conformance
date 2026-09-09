# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The requests workload every requests instrumentation here sends.

Shared by every implementation under ``requests/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

Only the send is this library's. The selected request and its answer are the
contract's, so a client is measured against exactly what a server scenario
would have answered. The shared telemetry contract checks what that request
emits.
"""

from __future__ import annotations

import requests

from otel_http_test_client import (
    REQUEST_TIMEOUT_SECONDS,
    client_headers,
    drive_selected,
    mock_server_url,
)


def run() -> None:
    """Send the contract request the runner selected, at the server it started."""
    with requests.Session() as session:

        def send(method: str, url: str, body: str | None) -> tuple[int, str]:
            # A 4xx or 5xx is what the contract asked for, so it comes back as
            # a status: requests raises for one only when told to.
            response = session.request(
                method,
                url,
                data=None if body is None else body.encode("utf-8"),
                headers=client_headers(body),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            return response.status_code, response.text

        drive_selected(mock_server_url(), send)
