// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the net/http server scenario with otelhttp
// instrumentation.
package main

import (
	"net/http"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/net-http/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariomain"
)

func main() {
	scenariomain.RunServer(func(stopping <-chan error) error {
		return scenarios.RunServer(func(handler http.Handler) http.Handler {
			// No operation name: otelhttp's default span name formatter
			// ignores it and names the span from the request method and the
			// route ServeMux reports.
			return otelhttp.NewHandler(handler, "")
		}, stopping)
	})
}
