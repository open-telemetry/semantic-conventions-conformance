// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the Echo server scenario with otelecho instrumentation.
package main

import (
	"go.opentelemetry.io/contrib/instrumentation/github.com/labstack/echo/otelecho"

	echoscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/echo/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariomain"
)

func main() {
	scenariomain.RunServer(func(stopping <-chan error) error {
		return echoscenarios.RunServer(otelecho.Middleware(""), stopping)
	})
}
