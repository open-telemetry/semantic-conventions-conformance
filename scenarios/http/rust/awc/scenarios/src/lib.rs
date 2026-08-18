// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! The awc client workload, with no OpenTelemetry dependency.

use std::fmt;
use std::future::Future;

use awc::http::Method;
use awc::{Client, ClientRequest};
use otel_conformance_http::{drive, ContractError, Response, CONTENT_TYPE, USER_AGENT};

/// Builds every measured request with awc and passes it to `send`.
///
/// # Errors
///
/// Returns an error when sending fails or a response differs from the contract.
///
/// # Panics
///
/// Panics when the committed shared contract contains an invalid HTTP method.
pub async fn run<F, Fut, E>(
    client: &Client,
    base_url: &str,
    mut send: F,
) -> Result<(), ContractError>
where
    F: FnMut(ClientRequest, Option<String>) -> Fut,
    Fut: Future<Output = Result<Response, E>>,
    E: fmt::Display,
{
    drive(base_url, |exchange, url| {
        let method = Method::from_bytes(exchange.method.as_bytes())
            .expect("the committed contract contains a valid HTTP method");
        let body = (!exchange.body.is_empty()).then_some(exchange.body);
        let mut request = client
            .request(method, url)
            .insert_header(("user-agent", USER_AGENT));
        // Only a request that carries a body describes its type, matching how
        // every language's client sends this same contract.
        if body.is_some() {
            request = request.insert_header(("content-type", CONTENT_TYPE));
        }
        send(request, body)
    })
    .await
}
