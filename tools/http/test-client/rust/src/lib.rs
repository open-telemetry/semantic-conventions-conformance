// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! The shared HTTP exchanges as Rust scenarios read and answer them.

use std::fmt;
use std::future::Future;
use std::sync::OnceLock;

use serde::Deserialize;
use serde_json::Value;

/// The media type every contract route returns.
pub const CONTENT_TYPE: &str = "application/json";
/// The fixed user agent used across scenario languages.
pub const USER_AGENT: &str = "otel-http-conformance/1";
/// The environment variable set by `otel-http-drive`.
pub const PORT_VARIABLE: &str = "OTEL_HTTP_SCENARIO_PORT";

const CONTRACT: &str = include_str!("../../contract.json");
const REQUEST_BODY_PLACEHOLDER: &str = "${requestBody}";

/// One concrete request and the answer the contract requires.
#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Exchange {
    pub description: String,
    pub method: String,
    pub path: String,
    #[serde(default)]
    pub body: String,
    pub status: u16,
    pub response_body: String,
    #[serde(default)]
    pub readiness: bool,
}

impl Exchange {
    fn rendered_response_body(&self, request_body: &str) -> String {
        let body = if request_body.is_empty() {
            "{}"
        } else {
            request_body
        };
        self.response_body.replace(REQUEST_BODY_PLACEHOLDER, body)
    }
}

/// A response returned by a sender or by [`respond`].
#[derive(Clone, Debug)]
pub struct Response {
    pub status: u16,
    pub body: String,
}

/// The contract is malformed, cannot be matched, or was answered incorrectly.
#[derive(Clone, Debug)]
pub struct ContractError {
    message: String,
}

impl ContractError {
    fn new(message: impl Into<String>) -> Self {
        Self {
            message: message.into(),
        }
    }
}

impl fmt::Display for ContractError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.message)
    }
}

impl std::error::Error for ContractError {}

#[derive(Deserialize)]
struct Document {
    requests: Vec<Exchange>,
}

static EXCHANGES: OnceLock<Result<Vec<Exchange>, String>> = OnceLock::new();

/// Returns every exchange, including the readiness request, in order.
///
/// # Errors
///
/// Returns an error when the embedded contract is invalid or empty.
pub fn exchanges() -> Result<&'static [Exchange], ContractError> {
    EXCHANGES
        .get_or_init(|| {
            let document: Document =
                serde_json::from_str(CONTRACT).map_err(|error| error.to_string())?;
            if document.requests.is_empty() {
                return Err("contract describes no requests".to_owned());
            }
            Ok(document.requests)
        })
        .as_deref()
        .map_err(|message| ContractError::new(format!("invalid contract.json: {message}")))
}

/// Returns the measured requests, excluding readiness, in order.
///
/// # Errors
///
/// Returns an error when the embedded contract is invalid or empty.
pub fn requests() -> Result<impl Iterator<Item = &'static Exchange>, ContractError> {
    Ok(exchanges()?.iter().filter(|exchange| !exchange.readiness))
}

/// Returns the contract answer for one concrete request.
///
/// # Errors
///
/// Returns an error when the embedded contract cannot be read.
pub fn respond(method: &str, path: &str, request_body: &str) -> Result<Response, ContractError> {
    let path = without_query(path);
    let exchange = exchanges()?
        .iter()
        .find(|exchange| exchange.method == method && without_query(&exchange.path) == path);
    Ok(exchange.map_or_else(
        || Response {
            status: 404,
            body: r#"{"message": "no such route"}"#.to_owned(),
        },
        |exchange| Response {
            status: exchange.status,
            body: exchange.rendered_response_body(request_body),
        },
    ))
}

/// Sends every measured request through a caller-supplied asynchronous sender.
///
/// # Errors
///
/// Returns an error when the base URL is blank, the sender fails, or a response
/// does not match the contract.
pub async fn drive<F, Fut, E>(base_url: &str, mut send: F) -> Result<(), ContractError>
where
    F: FnMut(Exchange, String) -> Fut,
    Fut: Future<Output = Result<Response, E>>,
    E: fmt::Display,
{
    if base_url.trim().is_empty() {
        return Err(ContractError::new("base URL must not be blank"));
    }
    for exchange in requests()? {
        let response = send(exchange.clone(), format!("{base_url}{}", exchange.path))
            .await
            .map_err(|error| {
                ContractError::new(format!("{} {}: {error}", exchange.method, exchange.path))
            })?;
        println!(
            "{} {} -> {} {}",
            exchange.method,
            exchange.path,
            response.status,
            abbreviate(&response.body)
        );
        verify(exchange, &response)?;
    }
    Ok(())
}

/// Checks one response against the exchange that describes it.
///
/// # Errors
///
/// Returns an error when the status or JSON response body differs.
pub fn verify(exchange: &Exchange, response: &Response) -> Result<(), ContractError> {
    if response.status != exchange.status {
        return Err(ContractError::new(format!(
            "{} {} answered {}, but the contract requires {}",
            exchange.method, exchange.path, response.status, exchange.status
        )));
    }
    let expected = parse_json(&exchange.rendered_response_body(&exchange.body))?;
    let actual = parse_json(&response.body)?;
    if actual != expected {
        return Err(ContractError::new(format!(
            "{} {} answered {actual}, but the contract requires {expected}",
            exchange.method, exchange.path
        )));
    }
    Ok(())
}

/// Returns the port that `otel-http-drive` selected for a server scenario.
///
/// # Errors
///
/// Returns an error when the environment variable is absent or not a valid
/// port.
pub fn scenario_port() -> Result<u16, ContractError> {
    let value = otel_conformance_scenario::require(PORT_VARIABLE)
        .map_err(|error| ContractError::new(error.to_string()))?;
    value.parse().map_err(|error| {
        ContractError::new(format!("{PORT_VARIABLE} is not a port number: {error}"))
    })
}

fn without_query(path: &str) -> &str {
    path.split_once('?').map_or(path, |(path, _)| path)
}

fn parse_json(body: &str) -> Result<Value, ContractError> {
    serde_json::from_str(body)
        .map_err(|error| ContractError::new(format!("not JSON ({error}): {}", abbreviate(body))))
}

fn abbreviate(value: &str) -> String {
    let single_line = value.replace(['\r', '\n'], " ");
    single_line.chars().take(60).collect()
}

#[cfg(test)]
mod tests {
    use super::{drive, exchanges, parse_json, requests, respond, verify, Response};

    #[test]
    fn contract_has_one_readiness_and_five_measured_requests() {
        assert_eq!(exchanges().expect("contract should parse").len(), 6);
        assert_eq!(requests().expect("contract should parse").count(), 5);
    }

    #[test]
    fn responding_echoes_the_post_body() {
        let response =
            respond("POST", "/items", r#"{"name":"widget"}"#).expect("the contract should answer");

        assert_eq!(response.status, 201);
        assert!(response.body.contains(r#""name":"widget""#));
    }

    #[tokio::test]
    async fn client_drive_checks_answers_from_the_server_half() {
        drive("http://example.test", |exchange, _url| async move {
            respond(&exchange.method, &exchange.path, &exchange.body)
        })
        .await
        .expect("both halves should agree");
    }

    #[test]
    fn verification_rejects_the_wrong_status() {
        let exchange = requests()
            .expect("contract should parse")
            .next()
            .expect("a measured request");
        let error = verify(
            exchange,
            &Response {
                status: 599,
                body: exchange.rendered_response_body(&exchange.body),
            },
        )
        .expect_err("the wrong status should fail");

        assert!(error.to_string().contains("599"));
    }

    #[test]
    fn invalid_json_errors_abbreviate_the_body() {
        let body = format!("<html>{}</html>", "x".repeat(1_000));
        let error = parse_json(&body).expect_err("HTML should not parse as JSON");

        assert!(error.to_string().len() < 200);
        assert!(!error.to_string().contains("</html>"));
    }
}
