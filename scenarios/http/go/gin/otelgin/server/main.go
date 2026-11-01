// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the Gin server scenario with otelgin instrumentation.
package main

import (
	"go.opentelemetry.io/contrib/instrumentation/github.com/gin-gonic/gin/otelgin"

	ginscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/gin/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariomain"
)

func main() {
	scenariomain.RunServer(func(stopping <-chan error) error {
		return ginscenarios.RunServer(otelgin.Middleware(""), stopping)
	})
}
