// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the Echo server scenario with otelecho instrumentation.
package main

import (
	"context"
	"errors"
	"log"
	"os"

	"go.opentelemetry.io/contrib/instrumentation/github.com/labstack/echo/otelecho"

	echoscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/echo/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/internal/httpserver"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariosdk"
)

func main() {
	stopping := make(chan error, 1)
	go func() { stopping <- scenario.WaitForEOF(os.Stdin) }()

	if err := run(context.Background(), stopping); err != nil {
		log.Fatal(err)
	}
}

func run(ctx context.Context, stopping <-chan error) (err error) {
	sdk, err := scenariosdk.Initialize(ctx)
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, sdk.Shutdown(ctx)) }()

	return echoscenarios.RunServer(
		otelecho.Middleware(httpserver.Host),
		stopping,
	)
}
