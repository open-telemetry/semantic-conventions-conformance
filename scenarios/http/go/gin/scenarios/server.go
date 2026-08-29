// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenarios defines Gin workloads independently of instrumentation.
package scenarios

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/internal/httpserver"
)

// RunServer hosts the shared HTTP exchanges with middleware until the driver
// says stop.
func RunServer(middleware gin.HandlerFunc, stopping <-chan error) error {
	return httpserver.Run(newHandler(middleware), stopping)
}

func newHandler(middleware gin.HandlerFunc) http.Handler {
	gin.SetMode(gin.ReleaseMode)
	server := gin.New()
	if middleware != nil {
		server.Use(middleware)
	}

	answer := func(context *gin.Context) {
		httpserver.Answer(context.Writer, context.Request)
	}
	server.GET("/health", answer)
	server.GET("/users/:userId", answer)
	server.POST("/items", answer)
	server.GET("/status/:code", answer)
	return server
}
