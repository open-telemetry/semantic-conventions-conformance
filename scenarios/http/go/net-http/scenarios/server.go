// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenarios defines net/http workloads independently of instrumentation.
//
// Instrumentation-specific commands supply the client transport or server
// middleware.
package scenarios

import (
	"net/http"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/internal/httpserver"
)

// Middleware wraps the whole mux, which is where a net/http instrumentation
// that starts server spans attaches.
type Middleware func(http.Handler) http.Handler

// routes declare the contract with ServeMux's method-and-template patterns.
// ServeMux records the matched pattern on the request for instrumentation.
var routes = []string{
	"GET /health",
	"GET /users/{userId}",
	"POST /items",
	"GET /status/{code}",
}

// RunServer hosts the shared HTTP exchanges until stopping reports that the
// driver said stop.
//
// The caller owns the stop source. Command entry points can wait on standard
// input, while in-process callers can use a channel they control.
func RunServer(middleware Middleware, stopping <-chan error) error {
	return httpserver.Run(newHandler(middleware), stopping)
}

func newHandler(middleware Middleware) http.Handler {
	if middleware == nil {
		middleware = func(handler http.Handler) http.Handler { return handler }
	}

	mux := http.NewServeMux()
	for _, pattern := range routes {
		mux.Handle(pattern, http.HandlerFunc(httpserver.Answer))
	}
	return middleware(mux)
}
