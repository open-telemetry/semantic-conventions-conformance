// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command client runs the net/http client scenario with otelhttp
// instrumentation.
package main

import (
	"net/http"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/net-http/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariomain"
)

func main() {
	scenariomain.Run(func() error {
		return scenarios.RunClient(func(base http.RoundTripper) http.RoundTripper {
			return otelhttp.NewTransport(base)
		})
	})
}
