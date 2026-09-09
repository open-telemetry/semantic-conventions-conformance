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
    shutdown_server(shutdown_sender, server, wait).await
}

async fn shutdown_server(
    shutdown_sender: oneshot::Sender<()>,
    server: tokio::task::JoinHandle<io::Result<()>>,
    wait: io::Result<()>,
) -> Result<(), BoxError> {
    if shutdown_sender.send(()).is_err() {
        server.await??;
        return Err(io::Error::new(
            io::ErrorKind::BrokenPipe,
            "Tower server stopped before the shutdown signal",
        )
        .into());
    }
    let server_result = server.await?;
    wait?;
    server_result?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::shutdown_server;
    use std::io;
    use tokio::sync::oneshot;
    use tokio::task::JoinError;

    #[tokio::test]
    async fn closed_shutdown_channel_preserves_server_error() {
        let (sender, receiver) = oneshot::channel();
        drop(receiver);
        let server = tokio::spawn(async { Err(io::Error::other("server failed")) });

        let error = shutdown_server(sender, server, Ok(())).await.unwrap_err();

        assert_eq!(
            error.downcast_ref::<io::Error>().unwrap().kind(),
            io::ErrorKind::Other
        );
        assert_eq!(error.to_string(), "server failed");
    }

    #[tokio::test]
    async fn closed_shutdown_channel_preserves_server_panic() {
        let (sender, receiver) = oneshot::channel();
        drop(receiver);
        let server = tokio::spawn(async { panic!("server task panicked") });

        let error = shutdown_server(sender, server, Ok(())).await.unwrap_err();

        assert!(error.downcast_ref::<JoinError>().unwrap().is_panic());
    }

    #[tokio::test]
    async fn closed_shutdown_channel_preserves_server_cancellation() {
        let (sender, receiver) = oneshot::channel();
        drop(receiver);
        let server = tokio::spawn(std::future::pending());
        server.abort();

        let error = shutdown_server(sender, server, Ok(())).await.unwrap_err();

        assert!(error.downcast_ref::<JoinError>().unwrap().is_cancelled());
    }

    #[tokio::test]
    async fn unexpected_successful_exit_reports_broken_pipe() {
        let (sender, receiver) = oneshot::channel();
        drop(receiver);
        let server = tokio::spawn(async { Ok(()) });

        let error = shutdown_server(sender, server, Ok(())).await.unwrap_err();

        assert_eq!(
            error.downcast_ref::<io::Error>().unwrap().kind(),
            io::ErrorKind::BrokenPipe
        );
        assert_eq!(
            error.to_string(),
            "Tower server stopped before the shutdown signal"
        );
    }

    #[tokio::test]
    async fn graceful_shutdown_succeeds() {
        let (sender, receiver) = oneshot::channel();
        let server = tokio::spawn(async {
            receiver.await.expect("shutdown signal");
            Ok(())
        });

        shutdown_server(sender, server, Ok(())).await.unwrap();
    }

    #[tokio::test]
    async fn graceful_shutdown_preserves_server_error() {
        let (sender, receiver) = oneshot::channel();
        let server = tokio::spawn(async {
            receiver.await.expect("shutdown signal");
            Err(io::Error::other("server failed"))
        });

        let error = shutdown_server(sender, server, Ok(())).await.unwrap_err();

        assert_eq!(error.to_string(), "server failed");
    }

    #[tokio::test]
    async fn graceful_shutdown_preserves_eof_error_priority() {
        let (sender, receiver) = oneshot::channel();
        let server = tokio::spawn(async {
            receiver.await.expect("shutdown signal");
            Err(io::Error::other("server failed"))
        });

        let error = shutdown_server(sender, server, Err(io::Error::other("stdin failed")))
            .await
            .unwrap_err();

        assert_eq!(error.to_string(), "stdin failed");
    }
}
