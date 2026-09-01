// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! The Axum/Tower server workload, with no OpenTelemetry dependency.

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
