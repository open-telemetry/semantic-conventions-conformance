// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command client sends the HTTP contract through otelhttp's round tripper.
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

	return scenarios.RunClient(func(base http.RoundTripper) http.RoundTripper {
		return otelhttp.NewTransport(base)
	})
}
