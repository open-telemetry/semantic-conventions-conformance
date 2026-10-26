// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenarios defines go-restful workloads independently of
// instrumentation.
package scenarios

import (
	"net/http"

	"github.com/emicklei/go-restful/v3"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/internal/httpserver"
)

// RunServer hosts the shared HTTP exchanges with filter until the driver says
// stop.
func RunServer(filter restful.FilterFunction, stopping <-chan error) error {
	return httpserver.Run(newHandler(filter), stopping)
}

func newHandler(filter restful.FilterFunction) http.Handler {
	container := restful.NewContainer()
	if filter != nil {
		container.Filter(filter)
	}

	service := new(restful.WebService)
	answer := func(request *restful.Request, response *restful.Response) {
		httpserver.Answer(response, request.Request)
	}
	service.Route(service.GET("/health").To(answer))
	service.Route(service.GET("/users/{userId}").To(answer))
	service.Route(service.POST("/items").To(answer))
	service.Route(service.GET("/status/{code}").To(answer))
	container.Add(service)
	return container
}
