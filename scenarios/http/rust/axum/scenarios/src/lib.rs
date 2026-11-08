// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! The Axum HTTP server workload, with no OpenTelemetry dependency.

use axum::body::{Body, Bytes};
use axum::http::{Method, StatusCode, Uri};
use axum::response::Response;
use axum::routing::{get, post};
use axum::Router;
use otel_conformance_http::{respond, CONTENT_TYPE};

type HandlerError = (StatusCode, String);

/// Declares every route through Axum's native router.
pub fn router() -> Router {
    Router::new()
        .route("/health", get(without_body))
        .route("/users/{user_id}", get(without_body))
        .route("/items", post(with_body))
        .route("/status/{status}", get(without_body))
}

async fn without_body(method: Method, uri: Uri) -> Result<Response, HandlerError> {
    answer(&method, &uri, "")
}

async fn with_body(method: Method, uri: Uri, body: Bytes) -> Result<Response, HandlerError> {
    let body =
        std::str::from_utf8(&body).map_err(|error| (StatusCode::BAD_REQUEST, error.to_string()))?;
    answer(&method, &uri, body)
}

fn answer(method: &Method, uri: &Uri, body: &str) -> Result<Response, HandlerError> {
    let response = respond(method.as_str(), uri.path(), body)
        .map_err(|error| (StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    Response::builder()
        .status(response.status)
        .header("content-type", CONTENT_TYPE)
        .body(Body::from(response.body))
        .map_err(|error| (StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))
}

#[cfg(test)]
mod tests {
    use axum::body::{to_bytes, Body, Bytes};
    use axum::http::{Request, StatusCode};
    use http_body_util::BodyExt;
    use otel_conformance_http::{exchanges, verify, Response, CONTENT_TYPE};
    use tower::ServiceExt;

    use super::router;

    #[tokio::test]
    async fn native_routes_answer_every_contract_exchange() {
        for exchange in exchanges().expect("contract should parse") {
            let request = Request::builder()
                .method(exchange.method.as_str())
                .uri(&exchange.path)
                .body(Body::from(exchange.body.clone()))
                .unwrap();
            let response = router().oneshot(request).await.unwrap();

            assert_eq!(response.headers()["content-type"], CONTENT_TYPE);
            let status = response.status().as_u16();
            let body = to_bytes(response.into_body(), usize::MAX).await.unwrap();
            verify(
                exchange,
                &Response {
                    status,
                    body: String::from_utf8(body.to_vec()).unwrap(),
                },
            )
            .expect("Axum routes should honor the shared contract");
        }
    }

    #[tokio::test]
    async fn unmatched_path_returns_not_found() {
        let request = Request::builder()
            .uri("/nothing/here")
            .body(Body::empty())
            .unwrap();

        let response = router().oneshot(request).await.unwrap();

        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn invalid_utf8_body_returns_bad_request() {
        let request = Request::builder()
            .method("POST")
            .uri("/items")
            .body(Body::from(Bytes::from_static(&[0xff])))
            .unwrap();

        let response = router().oneshot(request).await.unwrap();

        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        assert!(!response
            .into_body()
            .collect()
            .await
            .unwrap()
            .to_bytes()
            .is_empty());
    }
}
