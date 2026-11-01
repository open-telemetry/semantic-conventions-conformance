// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the net/http server scenario with no in-process
// instrumentation, for OBI to instrument from outside.
package main

import (
	"log"
	"os"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/net-http/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
)

func main() {
	if err := scenario.WaitAtGate(); err != nil {
		log.Fatal(err)
	}
	stopping := make(chan error, 1)
	go func() { stopping <- scenario.WaitForEOF(os.Stdin) }()
	if err := scenarios.RunServer(nil, stopping); err != nil {
		log.Fatal(err)
	}
}
