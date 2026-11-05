// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command client runs the net/http client scenario with no in-process
// instrumentation, for OBI to instrument from outside.
package main

import (
	"log"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/net-http/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
)

func main() {
	if err := scenario.Run(func() error { return scenarios.RunClient(nil) }); err != nil {
		log.Fatal(err)
	}
}
