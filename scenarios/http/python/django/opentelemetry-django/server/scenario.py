# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import sys
from pathlib import Path

from opentelemetry.instrumentation.django import DjangoInstrumentor
from otel_http_test_client import serve

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scenarios"))

from server import create_app  # noqa: E402

DjangoInstrumentor().instrument()
serve(create_app)
