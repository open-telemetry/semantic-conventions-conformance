// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenarios defines gorilla/mux workloads independently of
// instrumentation.
package scenarios

import (
	"net/http"

	"github.com/gorilla/mux"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/internal/httpserver"
)

// RunServer hosts the shared HTTP exchanges with middleware until the driver
// says stop.
func RunServer(middleware mux.MiddlewareFunc, stopping <-chan error) error {
	return httpserver.Run(newHandler(middleware), stopping)
}

func newHandler(middleware mux.MiddlewareFunc) http.Handler {
	router := mux.NewRouter()
	router.HandleFunc("/health", httpserver.Answer).Methods(http.MethodGet)
	router.HandleFunc("/users/{userId}", httpserver.Answer).Methods(http.MethodGet)
	router.HandleFunc("/items", httpserver.Answer).Methods(http.MethodPost)
	router.HandleFunc("/status/{code}", httpserver.Answer).Methods(http.MethodGet)
	if middleware != nil {
		router.Use(middleware)
	}
	return router
}
