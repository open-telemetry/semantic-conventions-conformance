// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package scenariosdk

import (
	"context"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"go.opentelemetry.io/otel"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/metric/metricdata"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
)

func TestInitializeRequiresAnExporterEndpoint(t *testing.T) {
	restoreGlobals(t)
	t.Setenv(EndpointVariable, "")
	if err := os.Unsetenv(EndpointVariable); err != nil {
		t.Fatal(err)
	}

	_, err := Initialize(context.Background())

	if err == nil || !strings.Contains(err.Error(), EndpointVariable) {
		t.Errorf("Initialize() returned %v, want an error naming %s", err, EndpointVariable)
	}
}

func TestShutdownExportsPendingSpansAndMetrics(t *testing.T) {
	traceExporter := &recordingSpanExporter{}
	metricExporter := &recordingMetricExporter{}
	sdk := &SDK{
		tracerProvider: sdktrace.NewTracerProvider(
			sdktrace.WithBatcher(traceExporter, sdktrace.WithBatchTimeout(time.Hour)),
		),
		meterProvider: sdkmetric.NewMeterProvider(
			sdkmetric.WithReader(sdkmetric.NewPeriodicReader(
				metricExporter,
				sdkmetric.WithInterval(time.Hour),
			)),
		),
	}

	_, span := sdk.tracerProvider.Tracer("test").Start(context.Background(), "pending")
	span.End()
	counter, err := sdk.meterProvider.Meter("test").Int64Counter("pending")
	if err != nil {
		t.Fatal(err)
	}
	counter.Add(context.Background(), 1)

	if err := sdk.Shutdown(context.Background()); err != nil {
		t.Fatal(err)
	}
	if traceExporter.exported == 0 {
		t.Error("Shutdown() exported no spans")
	}
	if metricExporter.exported == 0 {
		t.Error("Shutdown() exported no metrics")
	}
}

func restoreGlobals(t *testing.T) {
	t.Helper()
	tracerProvider := otel.GetTracerProvider()
	meterProvider := otel.GetMeterProvider()
	propagator := otel.GetTextMapPropagator()
	t.Cleanup(func() {
		otel.SetTracerProvider(tracerProvider)
		otel.SetMeterProvider(meterProvider)
		otel.SetTextMapPropagator(propagator)
	})
}

type recordingSpanExporter struct {
	exported int
}

func (e *recordingSpanExporter) ExportSpans(
	_ context.Context, spans []sdktrace.ReadOnlySpan,
) error {
	e.exported += len(spans)
	return nil
}

func (*recordingSpanExporter) Shutdown(context.Context) error { return nil }

type recordingMetricExporter struct {
	mu       sync.Mutex
	exported int
}

func (*recordingMetricExporter) Temporality(
	sdkmetric.InstrumentKind,
) metricdata.Temporality {
	return metricdata.CumulativeTemporality
}

func (*recordingMetricExporter) Aggregation(
	kind sdkmetric.InstrumentKind,
) sdkmetric.Aggregation {
	return sdkmetric.DefaultAggregationSelector(kind)
}

func (e *recordingMetricExporter) Export(
	_ context.Context, metrics *metricdata.ResourceMetrics,
) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	for _, scope := range metrics.ScopeMetrics {
		e.exported += len(scope.Metrics)
	}
	return nil
}

func (*recordingMetricExporter) ForceFlush(context.Context) error { return nil }

func (*recordingMetricExporter) Shutdown(context.Context) error { return nil }
