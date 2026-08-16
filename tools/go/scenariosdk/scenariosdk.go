// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenariosdk is the OpenTelemetry SDK a scenario configures for
// itself.
//
// Only a scenario measuring explicit library instrumentation needs this; one
// measuring an out-of-process agent gets its telemetry without linking any of
// it. Go has no autoconfiguration package in the SDK, so the wiring the runner
// depends on — OTLP over gRPC to the endpoint it injected, and a flush before
// the process exits — is written down once here rather than in each scenario.
package scenariosdk

import (
	"context"
	"errors"
	"fmt"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"

	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
)

// EndpointVariable is where the runner publishes the collector it started for
// this scenario. The exporters read it themselves; it is required here so a
// misconfigured run fails rather than exporting nowhere.
const EndpointVariable = "OTEL_EXPORTER_OTLP_ENDPOINT"

// SDK is the providers a scenario installed, and how it flushes them.
type SDK struct {
	tracerProvider *sdktrace.TracerProvider
	meterProvider  *sdkmetric.MeterProvider
}

// Initialize installs the SDK globally, failing early rather than exporting
// nowhere.
//
// Globally because that is where instrumentation libraries look by default, so
// a scenario's own code stays about the library under test rather than about
// plumbing a provider through it.
func Initialize(ctx context.Context) (*SDK, error) {
	if _, err := scenario.Require(EndpointVariable); err != nil {
		return nil, err
	}

	// gRPC without an explicit endpoint or protocol: the exporters read
	// OTEL_EXPORTER_OTLP_* themselves, and the runner injects the protocol it
	// started the collector with.
	spanExporter, err := otlptracegrpc.New(ctx)
	if err != nil {
		return nil, fmt.Errorf("creating the OTLP span exporter: %w", err)
	}
	metricExporter, err := otlpmetricgrpc.New(ctx)
	if err != nil {
		return nil, fmt.Errorf("creating the OTLP metric exporter: %w", err)
	}

	sdk := &SDK{
		tracerProvider: sdktrace.NewTracerProvider(
			sdktrace.WithBatcher(spanExporter),
		),
		// The reader's interval comes from OTEL_METRIC_EXPORT_INTERVAL, which
		// the runner sets so far out that only the flush below exports — one
		// scenario's metrics cannot be split across two reports.
		meterProvider: sdkmetric.NewMeterProvider(
			sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metricExporter)),
		),
	}
	otel.SetTracerProvider(sdk.tracerProvider)
	otel.SetMeterProvider(sdk.meterProvider)
	// What a real deployment runs with, so a client scenario sends the headers
	// an instrumentation is expected to inject.
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{}, propagation.Baggage{},
	))
	return sdk, nil
}

// Shutdown flushes everything the scenario produced.
//
// A scenario that exits without it reports less than it emitted, which reads
// as missing instrumentation rather than as a scenario bug.
func (s *SDK) Shutdown(ctx context.Context) error {
	return errors.Join(
		s.tracerProvider.Shutdown(ctx),
		s.meterProvider.Shutdown(ctx),
	)
}
