// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenarios is what the net/http client and server scenarios do, with
// no OpenTelemetry in it.
//
// Every instrumentation of net/http runs this same traffic; what differs is
// only how it is attached, which each launch package supplies as the hooks
// below. Whether an instrumentation is code or an out-of-process agent is
// therefore not something the workload knows about.
package scenarios

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strconv"
	"time"

	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
	httpcontract "github.com/open-telemetry/semantic-conventions-conformance/tools/http/test-client/go"
)

// Middleware wraps the whole mux, which is where a net/http instrumentation
// that starts server spans attaches.
type Middleware func(http.Handler) http.Handler

// routes are the framework-native declaration of the contract's paths.
//
// Go 1.22's ServeMux takes the method and the path template in the pattern
// itself, so this is the route in net/http's own model rather than a shape
// invented for the conformance run. ServeMux reports back the pattern a
// request matched, on the request, which is where an instrumentation reads
// http.route from — so the declaration below is the whole of what makes the
// route observable, with nothing to attach per route.
var routes = []string{
	"GET /health",
	"GET /users/{userId}",
	"POST /items",
	"GET /status/{code}",
}

const (
	// A server that never times out reading request headers is a lint finding
	// in its own right. An idle keep-alive connection needs no deadline,
	// because Shutdown closes idle connections when the driver says stop.
	readHeaderTimeout = 10 * time.Second

	// Leave enough time for the driver to report a shutdown error before its
	// own process timeout expires.
	shutdownTimeout = 10 * time.Second
)

// RunServer hosts the shared HTTP exchanges until the driver says stop.
//
// The requests are sent by otel-http-drive from another process, so nothing
// this binary links can instrument the sender and record client spans in a
// server scenario's report. It listens on the port the driver chose and shuts
// down when the driver closes its standard input, which is what gives the SDK
// a chance to flush.
func RunServer(middleware Middleware) error {
	if middleware == nil {
		middleware = func(handler http.Handler) http.Handler { return handler }
	}

	port, err := httpcontract.ScenarioPort()
	if err != nil {
		return err
	}
	if _, err := httpcontract.Exchanges(); err != nil {
		return err
	}

	mux := http.NewServeMux()
	for _, pattern := range routes {
		mux.Handle(pattern, answer())
	}

	listener, err := net.Listen("tcp", net.JoinHostPort("127.0.0.1", strconv.Itoa(port)))
	if err != nil {
		return fmt.Errorf("listening on port %d: %w", port, err)
	}

	server := &http.Server{
		Handler:           middleware(mux),
		ReadHeaderTimeout: readHeaderTimeout,
	}
	served := make(chan error, 1)
	go func() { served <- server.Serve(listener) }()

	stopping := make(chan error, 1)
	go func() { stopping <- scenario.WaitForEOF() }()

	var stopped error
	select {
	case err := <-served:
		// Serve gave up before the driver said stop, so nothing was ever going
		// to be measured. Reporting it here rather than going on to wait for
		// standard input is what turns a hang into a message: otherwise the
		// process would hold the port until the driver's timeout killed it,
		// and the one line explaining why would go with it.
		if err == nil {
			err = errors.New("the server stopped accepting connections")
		}
		return err
	case stopped = <-stopping:
	}

	shutdownContext, cancelShutdown := context.WithTimeout(context.Background(), shutdownTimeout)
	err = server.Shutdown(shutdownContext)
	cancelShutdown()
	if err != nil {
		stopped = errors.Join(stopped, fmt.Errorf("shutting down server: %w", err))
		if err := server.Close(); err != nil {
			stopped = errors.Join(stopped, fmt.Errorf("closing server: %w", err))
		}
	}
	if err := <-served; err != nil && !errors.Is(err, http.ErrServerClosed) {
		stopped = errors.Join(stopped, err)
	}
	return stopped
}

// answer looks the concrete request up in the contract. Identical for every Go
// framework, which is why only the route declaration above is net/http's.
func answer() http.Handler {
	return http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		body, err := io.ReadAll(request.Body)
		if err != nil {
			http.Error(writer, err.Error(), http.StatusBadRequest)
			return
		}
		response, err := httpcontract.Respond(request.Method, requestTarget(request), string(body))
		if err != nil {
			http.Error(writer, err.Error(), http.StatusInternalServerError)
			return
		}
		writer.Header().Set("Content-Type", httpcontract.ContentType)
		writer.WriteHeader(response.StatusCode)
		_, _ = io.WriteString(writer, response.Body)
	})
}

func requestTarget(request *http.Request) string {
	return request.URL.RequestURI()
}
