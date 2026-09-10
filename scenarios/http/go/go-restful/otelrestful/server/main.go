// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Command server runs the go-restful server scenario with otelrestful
// instrumentation.
package main

import (
	"go.opentelemetry.io/contrib/instrumentation/github.com/emicklei/go-restful/otelrestful"

	restfulscenarios "github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/go-restful/scenarios"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariomain"
)

func main() {
	scenariomain.RunServer(func(stopping <-chan error) error {
		return restfulscenarios.RunServer(otelrestful.OTelFilter(""), stopping)
	})
}
