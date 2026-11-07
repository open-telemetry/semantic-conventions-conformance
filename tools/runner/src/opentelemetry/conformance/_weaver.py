# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Weaver live-check lifecycle for the version pinned by this repo."""

from __future__ import annotations

import inspect
import logging
import time
from typing import Any, cast

from requests import get, post
from urllib3 import HTTPConnectionPool
from urllib3.exceptions import (
    ConnectTimeoutError,
    ProtocolError,
    ReadTimeoutError,
)
from urllib3.util import Timeout as HttpTimeout

from opentelemetry.test.weaver_live_check import LiveCheckReport
from opentelemetry.test.weaver_live_check import (
    WeaverLiveCheck as _WeaverLiveCheck,
)

from ._env import timeout_seconds

logger = logging.getLogger(__name__)

_STARTUP_TIMEOUT = ("OTEL_CONFORMANCE_WEAVER_STARTUP_TIMEOUT", 120.0)
_HEALTH_TIMEOUT_SECONDS = 1.0
_POLL_INTERVAL_SECONDS = 0.1

# opentelemetry-test-utils 0.66b2 has no startup_timeout. A later helper
# polls /health until that deadline. Weaver v0.28.0, the newest release,
# still binds /health only after registry resolution.
_PARENT_ACCEPTS_STARTUP_TIMEOUT = (
    "startup_timeout"
    in inspect.signature(_WeaverLiveCheck.__init__).parameters
)


class WeaverLiveCheck(_WeaverLiveCheck):
    def __init__(
        self,
        *args: Any,
        startup_timeout: float | None = None,
        **kwargs: Any,
    ) -> None:
        # Keep the local deadline even when the helper accepts the timeout.
        self._startup_timeout_fallback = startup_timeout
        if startup_timeout is not None and _PARENT_ACCEPTS_STARTUP_TIMEOUT:
            kwargs["startup_timeout"] = startup_timeout
        super().__init__(*args, **kwargs)

    def _wait_for_ready(self) -> None:
        assert self._process is not None
        passed = getattr(self, "_startup_timeout_fallback", None)
        startup = (
            float(passed)
            if isinstance(passed, (int, float))
            else timeout_seconds(*_STARTUP_TIMEOUT)
        )
        deadline = time.monotonic() + startup
        last_error: ConnectTimeoutError | ProtocolError | ReadTimeoutError | None = None
        exit_code: int | None = None
        with HTTPConnectionPool("127.0.0.1", self._admin_port) as health:
            while (remaining := deadline - time.monotonic()) > 0:
                exit_code = self._process.poll()
                if exit_code is not None:
                    break
                try:
                    with health.urlopen(
                        "GET",
                        "/health",
                        timeout=HttpTimeout(
                            total=min(_HEALTH_TIMEOUT_SECONDS, remaining)
                        ),
                        retries=False,
                        redirect=False,
                        preload_content=False,
                    ) as response:
                        ready = response.status == 200
                except (ConnectTimeoutError, ProtocolError, ReadTimeoutError) as exc:
                    last_error = exc
                    ready = False
                exit_code = self._process.poll()
                if exit_code is not None:
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if ready:
                    return
                time.sleep(min(_POLL_INTERVAL_SECONDS, remaining))
        if exit_code is not None:
            raise RuntimeError(
                f"WeaverLiveCheck process exited unexpectedly (code {exit_code})"
            )
        raise TimeoutError(
            f"WeaverLiveCheck did not become ready within {startup}s on "
            f"http://127.0.0.1:{self._admin_port}/health"
        ) from last_error

    def _do_stop(self, timeout: int) -> tuple[LiveCheckReport, int]:
        if not self._ready:
            raise RuntimeError("WeaverLiveCheck process did not start successfully")
        try:
            base_url = f"http://localhost:{self._admin_port}"
            response = post(f"{base_url}/stop", timeout=timeout)
            response.raise_for_status()
            payload: object = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError("Unexpected Weaver /stop response")
            stopped = cast("dict[str, object]", payload)
            if stopped.get("state") == "stopped":
                try:
                    if stopped.get("report") is not True:
                        raise RuntimeError("Weaver stopped without an HTTP report")
                    response = get(f"{base_url}/report", timeout=timeout)
                    response.raise_for_status()
                    report = LiveCheckReport(response.json())
                finally:
                    response = post(f"{base_url}/shutdown", timeout=timeout)
                    response.raise_for_status()
            elif "samples" in stopped and "statistics" in stopped:
                # Before 0.27, /stop returns the report and exits the process.
                report = LiveCheckReport(stopped)
            else:
                raise RuntimeError("Unexpected Weaver /stop response")
            assert self._process is not None
            exit_code = self._process.wait(timeout=timeout)
        except Exception as exc:
            logs = self._read_weaver_logs()
            logger.error("Error communicating with weaver: %s, logs: %s", exc, logs)
            raise
        return report, exit_code
