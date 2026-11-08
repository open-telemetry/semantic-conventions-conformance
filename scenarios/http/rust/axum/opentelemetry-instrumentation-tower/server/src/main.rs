// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

use std::error::Error;
use std::io;

use axum::{serve as axum_serve, Router};
use opentelemetry_instrumentation_tower::HTTPLayer;
use otel_conformance_scenario_sdk::ScenarioSdk;
use tokio::net::TcpListener;
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
    let app = axum_scenarios::router().layer(HTTPLayer::new());
    let listener = TcpListener::bind(("127.0.0.1", port)).await?;
    let (shutdown_sender, shutdown_receiver) = oneshot::channel();
    let server = tokio::spawn(serve(listener, app, shutdown_receiver));

    let wait = tokio::task::spawn_blocking(otel_conformance_scenario::wait_for_eof).await?;
    shutdown_server(shutdown_sender, server, wait).await
}

async fn serve(
    listener: TcpListener,
    app: Router,
    shutdown: oneshot::Receiver<()>,
) -> io::Result<()> {
    axum_serve(listener, app)
        .with_graceful_shutdown(async move {
            shutdown.await.ok();
        })
        .await
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
            "Axum server stopped before the shutdown signal",
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
    use super::{serve, shutdown_server};
    use std::io;
    use std::time::Duration;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::{TcpListener, TcpStream};
    use tokio::sync::oneshot;
    use tokio::task::JoinError;
    use tokio::time::timeout;

    #[tokio::test]
    async fn shutdown_finishes_an_inflight_request() {
        let listener = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
        let address = listener.local_addr().unwrap();
        let app =
            axum_scenarios::router().layer(opentelemetry_instrumentation_tower::HTTPLayer::new());
        let (sender, receiver) = oneshot::channel();
        let server = tokio::spawn(serve(listener, app, receiver));
        let mut client = TcpStream::connect(address).await.unwrap();
        client
            .write_all(
                b"POST /items HTTP/1.1\r\nHost: localhost\r\nContent-Length: 17\r\nExpect: 100-continue\r\n\r\n",
            )
            .await
            .unwrap();
        let mut interim = [0; 25];
        timeout(Duration::from_secs(5), client.read_exact(&mut interim))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(&interim, b"HTTP/1.1 100 Continue\r\n\r\n");

        sender.send(()).unwrap();
        client.write_all(br#"{"name":"widget"}"#).await.unwrap();
        let mut response = Vec::new();
        timeout(Duration::from_secs(5), client.read_to_end(&mut response))
            .await
            .unwrap()
            .unwrap();
        let response = String::from_utf8(response).unwrap();
        assert!(response.starts_with("HTTP/1.1 201 Created\r\n"));
        assert!(response.contains(r#""name":"widget""#));
        timeout(Duration::from_secs(5), server)
            .await
            .unwrap()
            .unwrap()
            .unwrap();
    }

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
            "Axum server stopped before the shutdown signal"
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
