// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenarios defines Echo workloads independently of instrumentation.
package scenarios

import (
	"net/http"

	"github.com/labstack/echo/v4"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/internal/httpserver"
)

// RunServer hosts the shared HTTP exchanges with middleware until the driver
// says stop.
func RunServer(middleware echo.MiddlewareFunc, stopping <-chan error) error {
	return httpserver.Run(newHandler(middleware), stopping)
}

func newHandler(middleware echo.MiddlewareFunc) http.Handler {
	server := echo.New()
	server.HideBanner = true
	server.HidePort = true
	if middleware != nil {
		server.Use(middleware)
	}

	answer := func(context echo.Context) error {
		httpserver.Answer(context.Response(), context.Request())
		return nil
	}
	server.GET("/health", answer)
	server.GET("/users/:userId", answer)
	server.POST("/items", answer)
	server.GET("/status/:code", answer)
	return server
}
