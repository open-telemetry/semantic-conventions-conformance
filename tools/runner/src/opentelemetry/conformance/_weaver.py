# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Weaver live-check lifecycle for the version pinned by this repo."""

from __future__ import annotations

import logging
from typing import cast

from requests import get, post

from opentelemetry.test.weaver_live_check import LiveCheckReport
from opentelemetry.test.weaver_live_check import (
    WeaverLiveCheck as _WeaverLiveCheck,
)

logger = logging.getLogger(__name__)


class WeaverLiveCheck(_WeaverLiveCheck):
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
