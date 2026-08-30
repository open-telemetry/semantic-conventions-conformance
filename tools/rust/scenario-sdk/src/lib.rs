// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! The global OpenTelemetry SDK used by explicitly instrumented Rust scenarios.

use std::env;
use std::error::Error;
use std::fmt;
use std::io;
use std::time::Duration;

use opentelemetry::global;
use opentelemetry_sdk::metrics::{PeriodicReader, SdkMeterProvider};
use opentelemetry_sdk::propagation::TraceContextPropagator;
use opentelemetry_sdk::trace::SdkTracerProvider;
use otel_conformance_scenario::require;

const ENDPOINT_VARIABLE: &str = "OTEL_EXPORTER_OTLP_ENDPOINT";
const METRIC_EXPORT_INTERVAL_VARIABLE: &str = "OTEL_METRIC_EXPORT_INTERVAL";
const DEFAULT_METRIC_EXPORT_INTERVAL_MILLIS: u64 = 2_147_483_647;

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
    /// Returns an error when the runner supplied no collector endpoint, the
    /// metric export interval is invalid, or an exporter cannot be constructed.
    pub fn initialize() -> Result<Self, Box<dyn Error>> {
        require(ENDPOINT_VARIABLE)?;

        let span_exporter = opentelemetry_otlp::SpanExporter::builder()
            .with_tonic()
            .build()?;
        let metric_exporter = opentelemetry_otlp::MetricExporter::builder()
            .with_tonic()
            .build()?;
        let metric_reader = PeriodicReader::builder(metric_exporter)
            .with_interval(metric_export_interval()?)
            .build();

        let tracer_provider = SdkTracerProvider::builder()
            .with_batch_exporter(span_exporter)
            .build();
        let meter_provider = SdkMeterProvider::builder()
            .with_reader(metric_reader)
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

fn metric_export_interval() -> Result<Duration, Box<dyn Error>> {
    match env::var(METRIC_EXPORT_INTERVAL_VARIABLE) {
        Ok(value) => Ok(parse_metric_export_interval(&value)?),
        Err(env::VarError::NotPresent) => {
            Ok(Duration::from_millis(DEFAULT_METRIC_EXPORT_INTERVAL_MILLIS))
        }
        Err(error) => Err(error.into()),
    }
}

fn parse_metric_export_interval(value: &str) -> io::Result<Duration> {
    value
        .parse::<u64>()
        .map(Duration::from_millis)
        .map_err(|error| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("{METRIC_EXPORT_INTERVAL_VARIABLE} is not milliseconds: {error}"),
            )
        })
}

#[cfg(test)]
mod tests {
    use super::parse_metric_export_interval;

    #[test]
    fn metric_export_interval_is_read_as_milliseconds() {
        let interval = parse_metric_export_interval("2147483647").expect("valid interval");

        assert_eq!(interval.as_millis(), 2_147_483_647);
    }

    #[test]
    fn invalid_metric_export_interval_names_the_variable() {
        let error = parse_metric_export_interval("later").expect_err("invalid interval");

        assert!(error.to_string().contains("OTEL_METRIC_EXPORT_INTERVAL"));
    }
}
