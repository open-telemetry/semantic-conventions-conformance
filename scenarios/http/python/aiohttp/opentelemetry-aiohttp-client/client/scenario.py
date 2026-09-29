# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path

from opentelemetry.instrumentation.aiohttp_client import (
    AioHttpClientInstrumentor,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scenarios"))

from client import run  # noqa: E402

AioHttpClientInstrumentor().instrument()
run()
