// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the net/http server scenario with no in-process
// instrumentation, for OBI to instrument from outside.
package main

import (
	"log"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/net-http/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
)

func main() {
	serve := func(stopping <-chan error) error { return scenarios.RunServer(nil, stopping) }
	if err := scenario.RunServer(serve); err != nil {
		log.Fatal(err)
	}
}
