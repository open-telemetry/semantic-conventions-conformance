# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""OTel SDK setup for Python HTTP conformance scenarios."""

import os

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def create_otlp_span_processor():
    """Build a BatchSpanProcessor that exports spans to the configured OTLP endpoint."""
    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]
    return BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))


def setup_otel(tracer_provider=None):
    """Configure OTel SDK with OTLP exporters.

    Returns (TracerProvider, LoggerProvider, MeterProvider).
    """
    endpoint = os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]

    tp = tracer_provider or TracerProvider()
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    if tracer_provider is None:
        trace.set_tracer_provider(tp)

    lp = LoggerProvider()
    lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, insecure=True)))
    set_logger_provider(lp)

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=5000,
    )
    mp = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(mp)

    return tp, lp, mp


def flush_and_shutdown_span_processor(processor):
    """Flush and shut down a standalone span processor."""
    print("Flushing telemetry...")
    processor.force_flush()
    processor.shutdown()
    print("Done.")


def flush_and_shutdown(tp, lp, mp):
    """Flush and shut down all OTel providers."""
    print("Flushing telemetry...")
    tp.force_flush(timeout_millis=5000)
    lp.force_flush(timeout_millis=5000)
    mp.force_flush(timeout_millis=5000)
    tp.shutdown()
    lp.shutdown()
    mp.shutdown()
    print("Done.")
