# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path

from opentelemetry.instrumentation.aiohttp_server import (
    AioHttpServerInstrumentor,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scenarios"))

from server import create_app, serve  # noqa: E402

AioHttpServerInstrumentor().instrument()
serve(create_app)
