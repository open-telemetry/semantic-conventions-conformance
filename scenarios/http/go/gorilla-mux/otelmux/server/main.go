// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the gorilla/mux server scenario with otelmux
// instrumentation.
package main

import (
	"go.opentelemetry.io/contrib/instrumentation/github.com/gorilla/mux/otelmux"

	muxscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/gorilla-mux/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariomain"
)

func main() {
	scenariomain.RunServer(func(stopping <-chan error) error {
		return muxscenarios.RunServer(otelmux.Middleware(""), stopping)
	})
}
