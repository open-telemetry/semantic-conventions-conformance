// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package httpservertest verifies Go HTTP framework handlers against the shared
// conformance contract.
package httpservertest

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	httpcontract "github.com/open-telemetry/semantic-conventions-conformance/tools/http/test-client/go"
)

// AssertContract verifies that handler answers every exchange in the contract.
func AssertContract(t *testing.T, handler http.Handler) {
	t.Helper()

	exchanges, err := httpcontract.Exchanges()
	if err != nil {
		t.Fatal(err)
	}
	for _, exchange := range exchanges {
		t.Run(exchange.Method+" "+exchange.Path, func(t *testing.T) {
			request := httptest.NewRequest(
				exchange.Method,
				"http://example.test"+exchange.Path,
				strings.NewReader(exchange.Body),
			)
			response := httptest.NewRecorder()

			handler.ServeHTTP(response, request)

			if response.Code != exchange.Status {
				t.Errorf("status = %d, want %d", response.Code, exchange.Status)
			}
			result := response.Result()
			body, err := io.ReadAll(result.Body)
			closeErr := result.Body.Close()
			if err != nil {
				t.Fatal(err)
			}
			if closeErr != nil {
				t.Fatal(closeErr)
			}
			want := exchange.RenderResponseBody(exchange.Body)
			if string(body) != want {
				t.Errorf("body = %q, want %q", body, want)
			}
			if got := result.Header.Get("Content-Type"); got != httpcontract.ContentType {
				t.Errorf("Content-Type = %q, want %q", got, httpcontract.ContentType)
			}
		})
	}
}
