# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared client driver for HTTP server conformance scenarios."""

from __future__ import annotations

import http.client
import time
import urllib.error
import urllib.request

STANDARD_POST_PAYLOAD = '{"name": "widget"}'


def wait_for_health(base_url: str, attempts: int = 50, interval_seconds: float = 0.1) -> None:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1):
                return
        except (OSError, http.client.HTTPException):
            # The server is still starting up: connection refused, reset, or a
            # truncated response are all expected until it is listening.
            time.sleep(interval_seconds)
    raise RuntimeError(f"Test server failed to start: {base_url}")


def request_url(method: str, url: str, payload: str | None = None) -> tuple[int, str]:
    data = None if payload is None else payload.encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def run_standard_scenarios(base_url: str) -> None:
    _run_sync_scenario("GET", "basic request", f"{base_url}/users/123")
    _run_sync_scenario("POST", "create resource", f"{base_url}/items", STANDARD_POST_PAYLOAD)
    _run_sync_scenario("GET", "404 error", f"{base_url}/status/404")
    _run_sync_scenario("GET", "500 server error", f"{base_url}/status/500")


def _run_sync_scenario(method: str, label: str, url: str, payload: str | None = None) -> None:
    print(f"  [{method}] {label}")
    status, body = request_url(method, url, payload)
    print(f"    -> {status}: {body[:60]}")
