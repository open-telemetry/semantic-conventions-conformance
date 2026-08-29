// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use std::error::Error;
use std::io;

use opentelemetry_instrumentation_tower::HTTPLayer;
use otel_conformance_scenario_sdk::ScenarioSdk;
use tokio::sync::oneshot;

type BoxError = Box<dyn Error>;

#[tokio::main]
async fn main() -> Result<(), BoxError> {
    let sdk = ScenarioSdk::initialize()?;
    let result = run().await;
    let shutdown = tokio::task::spawn_blocking(move || sdk.shutdown()).await?;
    result?;
    shutdown?;
    Ok(())
}

async fn run() -> Result<(), BoxError> {
    let port = otel_conformance_http::scenario_port()?;
    let app = tower_scenarios::router().layer(HTTPLayer::new());
    let listener = tokio::net::TcpListener::bind(("127.0.0.1", port)).await?;
    let (shutdown_sender, shutdown_receiver) = oneshot::channel();
    let server = tokio::spawn(async move {
        axum::serve(listener, app)
            .with_graceful_shutdown(async move {
                shutdown_receiver.await.ok();
            })
            .await
    });

    let wait = tokio::task::spawn_blocking(otel_conformance_scenario::wait_for_eof).await?;
    shutdown_sender.send(()).map_err(|()| {
        io::Error::new(
            io::ErrorKind::BrokenPipe,
            "Tower server stopped before the shutdown signal",
        )
    })?;
    let server_result = server.await?;
    wait?;
    server_result?;
    Ok(())
}
