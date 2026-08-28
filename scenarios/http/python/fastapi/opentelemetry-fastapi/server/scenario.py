# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

python_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(python_root / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scenarios"))

from asgi_server import serve  # noqa: E402
from server import create_app  # noqa: E402


def instrumented() -> FastAPI:
    app = create_app()
    FastAPIInstrumentor().instrument_app(app)
    return app


serve(instrumented)
