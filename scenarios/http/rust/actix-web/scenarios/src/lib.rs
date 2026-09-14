// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! The Actix Web server workload, with no OpenTelemetry dependency.

use actix_web::http::StatusCode;
use actix_web::{error, web, HttpRequest, HttpResponse};
use otel_conformance_http::{respond, CONTENT_TYPE};

/// Declares every route through Actix Web's native router.
pub fn configure(config: &mut web::ServiceConfig) {
    config
        .route("/health", web::get().to(without_body))
        .route("/users/{user_id}", web::get().to(without_body))
        .route("/items", web::post().to(with_body))
        .route("/status/{status}", web::get().to(without_body));
}

async fn without_body(request: HttpRequest) -> actix_web::Result<HttpResponse> {
    answer(&request, "")
}

async fn with_body(request: HttpRequest, body: web::Bytes) -> actix_web::Result<HttpResponse> {
    let body = std::str::from_utf8(&body).map_err(error::ErrorBadRequest)?;
    answer(&request, body)
}

fn answer(request: &HttpRequest, body: &str) -> actix_web::Result<HttpResponse> {
    let response = respond(request.method().as_str(), request.uri().path(), body)
        .map_err(error::ErrorInternalServerError)?;
    let status = StatusCode::from_u16(response.status).map_err(error::ErrorInternalServerError)?;
    Ok(HttpResponse::build(status)
        .content_type(CONTENT_TYPE)
        .body(response.body))
}
