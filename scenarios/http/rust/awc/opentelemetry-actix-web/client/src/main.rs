// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use std::error::Error;

use opentelemetry_instrumentation_actix_web::ClientExt as _;
use otel_conformance_http::Response;
use otel_conformance_scenario_sdk::ScenarioSdk;

type BoxError = Box<dyn Error>;

#[actix_web::main]
async fn main() -> Result<(), BoxError> {
    let sdk = ScenarioSdk::initialize()?;
    let result = run().await;
    let shutdown = actix_web::rt::task::spawn_blocking(move || sdk.shutdown()).await?;
    shutdown?;
    result
}

async fn run() -> Result<(), BoxError> {
    let base_url = otel_conformance_scenario::require("MOCK_SERVER_URL")?;
    let client = awc::Client::new();
    awc_scenarios::run(&client, &base_url, |request, body| async move {
        let mut response = if let Some(body) = body {
            request.trace_request().send_body(body).await?
        } else {
            request.trace_request().send().await?
        };
        let status = response.status().as_u16();
        let body = response.body().await?;
        let body = String::from_utf8(body.to_vec())?;
        Ok::<_, BoxError>(Response { status, body })
    })
    .await?;
    Ok(())
}
