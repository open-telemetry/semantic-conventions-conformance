// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use std::error::Error;

use actix_web::{App, HttpServer};
use opentelemetry_instrumentation_actix_web::{RequestMetrics, RequestTracing};
use otel_conformance_scenario_sdk::ScenarioSdk;

type BoxError = Box<dyn Error>;

#[actix_web::main]
async fn main() -> Result<(), BoxError> {
    let sdk = ScenarioSdk::initialize()?;
    let result = run().await;
    let shutdown = actix_web::rt::task::spawn_blocking(move || sdk.shutdown()).await?;
    result?;
    shutdown?;
    Ok(())
}

async fn run() -> Result<(), BoxError> {
    let port = otel_conformance_http::scenario_port()?;
    let server = HttpServer::new(|| {
        App::new()
            .wrap(RequestTracing::new())
            .wrap(RequestMetrics::default())
            .configure(actix_web_scenarios::configure)
    })
    .bind(("127.0.0.1", port))?
    .run();
    let handle = server.handle();
    actix_web::rt::spawn(server);

    let eof = actix_web::rt::task::spawn_blocking(otel_conformance_scenario::wait_for_eof).await;
    handle.stop(true).await;
    eof??;
    Ok(())
}
