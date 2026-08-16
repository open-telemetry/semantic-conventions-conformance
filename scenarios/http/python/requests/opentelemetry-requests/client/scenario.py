# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Sends the shared requests workload with the requests instrumentation on.

``otel-conformance-python`` installs the SDK and nothing else, so this is
where the one instrumentation under test is turned on — explicitly, the way an
application using library instrumentation does, and the reason this package's
coverage is about that instrumentation alone.
"""

from __future__ import annotations

from client import run

from opentelemetry.instrumentation.requests import RequestsInstrumentor

RequestsInstrumentor().instrument()
run()
