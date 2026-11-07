// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the gorilla/mux server scenario with no in-process
// instrumentation, for OBI to instrument from outside.
package main

import (
	"log"

	muxscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/gorilla-mux/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
)

func main() {
	serve := func(stopping <-chan error) error { return muxscenarios.RunServer(nil, stopping) }
	if err := scenario.RunServer(serve); err != nil {
		log.Fatal(err)
	}
}
