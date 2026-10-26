// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the Echo server scenario with echo-otel instrumentation.
package main

import (
	echootel "github.com/labstack/echo-otel/v5"

	echoscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/echo/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariomain"
)

func main() {
	scenariomain.RunServer(func(stopping <-chan error) error {
		return echoscenarios.RunServer(echootel.NewMiddleware(""), stopping)
	})
}
