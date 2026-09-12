# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-python <scenario.py>`` — run a Python scenario program.

Installs global providers exporting over OTLP, then executes the program. It
sits *behind* the runner's environment contract rather than being part of it:
everything it needs — the endpoint and the metric export interval — arrives as
environment variables, so another language's SDK autoconfiguration reads the
same values.

The scenario program itself installs no providers; it picks up the globals
this module sets, which also exercises the zero-config path.
"""

from __future__ import annotations

import os
import runpy
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from opentelemetry import _logs, metrics, trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# Effectively infinite, so a periodic export can't split a scenario's metrics
# across reports — the flush at the end of a run exports them. The runner sets
# OTEL_METRIC_EXPORT_INTERVAL to the same value for every language; this is
# only the fallback for running a scenario by hand, outside a session.
METRIC_EXPORT_INTERVAL_MILLIS = 2**31 - 1
FLUSH_TIMEOUT_MILLIS = 15_000


def _install_providers(
    endpoint: str,
) -> tuple[TracerProvider, MeterProvider, LoggerProvider]:
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (  # noqa: PLC0415
        OTLPLogExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (  # noqa: PLC0415
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # noqa: PLC0415
        OTLPSpanExporter,
    )

    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )

    meter_provider = MeterProvider(
        metric_readers=[
            PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=endpoint, insecure=True),
                export_interval_millis=int(
                    os.environ.get(
                        "OTEL_METRIC_EXPORT_INTERVAL",
                        METRIC_EXPORT_INTERVAL_MILLIS,
                    )
                ),
            )
        ]
    )

    logger_provider = LoggerProvider()
    logger_provider.add_log_record_processor(
        SimpleLogRecordProcessor(
            OTLPLogExporter(endpoint=endpoint, insecure=True)
        )
    )

    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)
    _logs.set_logger_provider(logger_provider)
    return tracer_provider, meter_provider, logger_provider


def _flush_before_shutdown(
    providers: tuple[TracerProvider, MeterProvider, LoggerProvider],
    timeout_millis: int = FLUSH_TIMEOUT_MILLIS,
) -> None:
    tracer_provider, meter_provider, logger_provider = providers
    deadline = time.monotonic() + timeout_millis / 1000

    remaining_millis = max(0, int((deadline - time.monotonic()) * 1000))
    with ThreadPoolExecutor(max_workers=2) as executor:
        traces = executor.submit(
            tracer_provider.force_flush, timeout_millis=remaining_millis
        )
        logs = executor.submit(
            logger_provider.force_flush, timeout_millis=remaining_millis
        )

    for signal, result in (("trace", traces.result()), ("log", logs.result())):
        if not result:
            raise RuntimeError(
                f"{signal} flush did not complete within the shutdown budget"
            )

    remaining_millis = max(0, int((deadline - time.monotonic()) * 1000))
    if not meter_provider.force_flush(timeout_millis=remaining_millis):
        raise RuntimeError(
            "metric flush did not complete within the shutdown budget"
        )


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        raise SystemExit(f"usage: {sys.argv[0]} <scenario.py>")

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        raise SystemExit("OTEL_EXPORTER_OTLP_ENDPOINT is not set")

    providers = _install_providers(endpoint)
    try:
        runpy.run_path(argv[0], run_name="__main__")
    finally:
        try:
            _flush_before_shutdown(providers)
        finally:
            tracer_provider, meter_provider, logger_provider = providers
            tracer_provider.shutdown()
            logger_provider.shutdown()
            meter_provider.shutdown()
    return 0


def cli() -> None:
    """Console-script entry point."""
    sys.exit(main(sys.argv[1:]))


if __name__ == "__main__":
    cli()
