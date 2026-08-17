# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Serves the shared Flask app with the Flask instrumentation attached.

``otel-conformance-python`` installs the SDK and nothing else, so this is
where the one instrumentation under test is turned on — explicitly, the way an
application using library instrumentation does, and the reason this package's
coverage is about that instrumentation alone.

``otel-http-drive`` runs this from its own process and sends the contract at
it from outside, so nothing loaded here can instrument the sender.
"""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Flask

from opentelemetry.instrumentation.flask import FlaskInstrumentor
from otel_http_test_client import serve

# The workload every instrumentation of this library shares, which is beside
# them rather than in any one of them. Found from this file rather than from
# `PYTHONPATH`, which a machine that already exports one would replace.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scenarios"))

from server import create_app  # noqa: E402


def instrumented() -> Flask:
    app = create_app()
    FlaskInstrumentor().instrument_app(app)
    return app


serve(instrumented)
