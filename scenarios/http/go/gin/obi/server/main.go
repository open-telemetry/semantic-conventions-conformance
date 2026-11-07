// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the Gin server scenario with no in-process
// instrumentation, for OBI to instrument from outside.
package main

import (
	"log"

	ginscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/gin/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
)

func main() {
	serve := func(stopping <-chan error) error { return ginscenarios.RunServer(nil, stopping) }
	if err := scenario.RunServer(serve); err != nil {
		log.Fatal(err)
	}
}
