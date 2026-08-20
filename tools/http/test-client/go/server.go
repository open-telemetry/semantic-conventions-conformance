// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package httpcontract

import (
	"fmt"
	"os"
	"strconv"
)

// PortVariable names the port a server scenario listens on. otel-http-drive
// chooses it, which is what lets different scenarios run in parallel without
// colliding.
const PortVariable = "OTEL_HTTP_SCENARIO_PORT"

// Respond is what the contract answers to one request.
//
// A server scenario declares routes with the framework under test — that
// declaration is what an instrumentation reads http.route from — and then asks
// this function what to answer. Every Go framework therefore agrees on the
// statuses and bodies without forcing its route construction into a shared
// runtime model. requestBody is empty for a request that carried none.
//
// The requests are sent by otel-http-drive from another process, which checks
// each answer against the same contract. Respond returns an error when that
// contract cannot be loaded.
func Respond(method, path, requestBody string) (Response, error) {
	exchange, found, err := Lookup(method, path)
	if err != nil {
		return Response{}, err
	}
	if !found {
		return Response{StatusCode: 404, Body: `{"message": "no such route"}`}, nil
	}
	return Response{
		StatusCode: exchange.Status,
		Body:       exchange.RenderResponseBody(requestBody),
	}, nil
}

// ScenarioPort is the port the driver told this scenario to listen on.
func ScenarioPort() (int, error) {
	value := os.Getenv(PortVariable)
	if value == "" {
		return 0, fmt.Errorf(
			"%s is not set — a server scenario is started by `otel-http-drive`, "+
				"which chooses the port", PortVariable)
	}
	port, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("%s is not a port number: %w", PortVariable, err)
	}
	return port, nil
}
