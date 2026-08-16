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

from flask import Flask
from server import create_app

from opentelemetry.instrumentation.flask import FlaskInstrumentor
from otel_http_test_client import serve


def instrumented() -> Flask:
    app = create_app()
    FlaskInstrumentor().instrument_app(app)
    return app


serve(instrumented)
