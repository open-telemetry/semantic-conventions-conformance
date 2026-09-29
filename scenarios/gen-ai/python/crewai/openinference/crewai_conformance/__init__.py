# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""An OTLP exporter that takes the crew id out of a span name.

OpenInference names a crew's span after the crew's id, which CrewAI generates
per run and refuses to let a caller set. The name would differ on every run,
and so would every finding quoting it, which leaves the committed `data.json`
impossible to reproduce and the build red.

Renaming on the way out is the narrowest place to do it: the run still records
what the instrumentation emitted, and only the part that cannot be held still
is replaced. It is registered as a traces exporter so zero-code selects it by
name and the shared scenarios stay unaware of it. A hack, and it goes away if
the span name stops carrying an id.
"""

from __future__ import annotations

import re
from typing import Sequence

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult

_RUN_ID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


class StripRunIdsSpanExporter(OTLPSpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            span._name = _RUN_ID.sub("<id>", span.name)  # noqa: SLF001
        return super().export(spans)
