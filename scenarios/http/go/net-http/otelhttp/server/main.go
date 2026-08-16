// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server hosts the HTTP contract with otelhttp's server handler.
package main

import (
	"context"
	"errors"
	"log"
	"net/http"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/net-http/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariosdk"
)

func main() {
	if err := run(context.Background()); err != nil {
		log.Fatal(err)
	}
}

func run(ctx context.Context) (err error) {
	sdk, err := scenariosdk.Initialize(ctx)
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, sdk.Shutdown(ctx)) }()

	return scenarios.RunServer(func(handler http.Handler) http.Handler {
		// No operation name: otelhttp names a span from the route ServeMux
		// reports, and one supplied here would replace it on every span.
		return otelhttp.NewHandler(handler, "")
	})
}
