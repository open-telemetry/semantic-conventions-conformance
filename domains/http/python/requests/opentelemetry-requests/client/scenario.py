# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Sends the shared requests workload with the requests instrumentation on.

``otel-conformance-python`` installs the SDK and nothing else, so this is
where the one instrumentation under test is turned on — explicitly, the way an
application using library instrumentation does, and the reason this package's
coverage is about that instrumentation alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

from opentelemetry.instrumentation.requests import RequestsInstrumentor

# The workload every instrumentation of this library shares, which is beside
# them rather than in any one of them. Found from this file rather than from
# `PYTHONPATH`, which a machine that already exports one would replace.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scenarios"))

from client import run  # noqa: E402

RequestsInstrumentor().instrument()
run()
