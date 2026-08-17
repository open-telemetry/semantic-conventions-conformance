// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! The global OpenTelemetry SDK used by explicitly instrumented Rust scenarios.

use std::error::Error;
use std::fmt;

use opentelemetry::global;
use opentelemetry_sdk::metrics::SdkMeterProvider;
use opentelemetry_sdk::propagation::TraceContextPropagator;
use opentelemetry_sdk::trace::SdkTracerProvider;
use otel_conformance_scenario::require;

const ENDPOINT_VARIABLE: &str = "OTEL_EXPORTER_OTLP_ENDPOINT";

/// The providers installed globally for instrumentation libraries.
pub struct ScenarioSdk {
    tracer_provider: SdkTracerProvider,
    meter_provider: SdkMeterProvider,
}

/// A failure while flushing one or both providers.
#[derive(Debug)]
pub struct ShutdownError {
    messages: Vec<String>,
}

impl fmt::Display for ShutdownError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            formatter,
            "shutting down OpenTelemetry: {}",
            self.messages.join("; ")
        )
    }
}

impl Error for ShutdownError {}

impl ScenarioSdk {
    /// Builds OTLP gRPC exporters and installs both providers globally.
    ///
    /// # Errors
    ///
    /// Returns an error when the runner supplied no collector endpoint or an
    /// exporter cannot be constructed.
    pub fn initialize() -> Result<Self, Box<dyn Error>> {
        require(ENDPOINT_VARIABLE)?;

        let span_exporter = opentelemetry_otlp::SpanExporter::builder()
            .with_tonic()
            .build()?;
        let metric_exporter = opentelemetry_otlp::MetricExporter::builder()
            .with_tonic()
            .build()?;

        let tracer_provider = SdkTracerProvider::builder()
            .with_batch_exporter(span_exporter)
            .build();
        let meter_provider = SdkMeterProvider::builder()
            .with_periodic_exporter(metric_exporter)
            .build();

        global::set_tracer_provider(tracer_provider.clone());
        global::set_meter_provider(meter_provider.clone());
        global::set_text_map_propagator(TraceContextPropagator::new());

        Ok(Self {
            tracer_provider,
            meter_provider,
        })
    }

    /// Flushes and stops every provider, attempting both even if one fails.
    ///
    /// # Errors
    ///
    /// Returns every trace or metric provider shutdown failure.
    pub fn shutdown(self) -> Result<(), ShutdownError> {
        let mut messages = Vec::new();
        if let Err(error) = self.tracer_provider.shutdown() {
            messages.push(format!("traces: {error}"));
        }
        if let Err(error) = self.meter_provider.shutdown() {
            messages.push(format!("metrics: {error}"));
        }
        if messages.is_empty() {
            Ok(())
        } else {
            Err(ShutdownError { messages })
        }
    }
}
