// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//! The Tower HTTP server workload, with no OpenTelemetry dependency.

use std::error::Error;

use http::{Request, Response, StatusCode};
use http_body_util::{BodyExt, Full};
use hyper::body::{Body, Bytes};
use otel_conformance_http::{respond, CONTENT_TYPE};

type BoxError = Box<dyn Error + Send + Sync>;

/// Answers an HTTP request using the shared contract, without route metadata.
///
/// # Errors
///
/// Returns an error when the body cannot be read, the contract is invalid, or
/// the response cannot be constructed.
pub async fn answer<B>(request: Request<B>) -> Result<Response<Full<Bytes>>, BoxError>
where
    B: Body<Data = Bytes> + Send,
    B::Error: Error + Send + Sync + 'static,
{
    let (parts, body) = request.into_parts();
    let bytes = body.collect().await?.to_bytes();
    let body = match std::str::from_utf8(&bytes) {
        Ok(body) => body,
        Err(error) => {
            return Ok(Response::builder()
                .status(StatusCode::BAD_REQUEST)
                .header("content-type", "text/plain")
                .body(Full::new(Bytes::from(error.to_string())))?);
        }
    };
    let response = respond(parts.method.as_str(), parts.uri.path(), body)?;
    Ok(Response::builder()
        .status(response.status)
        .header("content-type", CONTENT_TYPE)
        .body(Full::new(Bytes::from(response.body)))?)
}

#[cfg(test)]
mod tests {
    use super::answer;
    use http::{Request, StatusCode};
    use http_body_util::{BodyExt, Full};
    use hyper::body::Bytes;
    use otel_conformance_http::{exchanges, verify, Response, CONTENT_TYPE};
    use tower::{service_fn, ServiceExt};

    #[tokio::test]
    async fn service_answers_every_contract_exchange() {
        for exchange in exchanges().expect("contract should parse") {
            let request = Request::builder()
                .method(exchange.method.as_str())
                .uri(&exchange.path)
                .body(Full::new(Bytes::from(exchange.body.clone())))
                .unwrap();
            assert!(request.extensions().is_empty());
            let response = service_fn(answer).oneshot(request).await.unwrap();
            assert_eq!(response.headers()["content-type"], CONTENT_TYPE);
            assert!(response.extensions().is_empty());
            let status = response.status().as_u16();
            let body = response.into_body().collect().await.unwrap().to_bytes();
            verify(
                exchange,
                &Response {
                    status,
                    body: String::from_utf8(body.to_vec()).unwrap(),
                },
            )
            .expect("service should honor the shared contract");
        }
    }

    #[tokio::test]
    async fn unknown_path_returns_not_found() {
        let request = Request::builder()
            .uri("/nothing/here")
            .body(Full::new(Bytes::new()))
            .unwrap();
        let response = service_fn(answer).oneshot(request).await.unwrap();

        assert_eq!(response.status(), StatusCode::NOT_FOUND);
    }

    #[tokio::test]
    async fn invalid_utf8_body_returns_bad_request() {
        let request = Request::builder()
            .method("POST")
            .uri("/items")
            .body(Full::new(Bytes::from_static(&[0xff])))
            .unwrap();
        let response = service_fn(answer).oneshot(request).await.unwrap();

        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        assert_eq!(response.headers()["content-type"], "text/plain");
        assert!(!response
            .into_body()
            .collect()
            .await
            .unwrap()
            .to_bytes()
            .is_empty());
    }
}
