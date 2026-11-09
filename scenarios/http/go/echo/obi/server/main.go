// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the Echo server scenario with no in-process
// instrumentation, for OBI to instrument from outside.
package main

import (
	"log"

	echoscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/echo/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
)

func main() {
	serve := func(stopping <-chan error) error { return echoscenarios.RunServer(nil, stopping) }
	if err := scenario.RunServer(serve); err != nil {
		log.Fatal(err)
	}
}
