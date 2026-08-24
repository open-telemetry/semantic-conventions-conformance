// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenarios defines net/http workloads independently of instrumentation.
//
// Instrumentation-specific commands supply the client transport or server
// middleware.
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

// routes declare the contract with ServeMux's method-and-template patterns.
// ServeMux records the matched pattern on the request for instrumentation.
var routes = []string{
	"GET /health",
	"GET /users/{userId}",
	"POST /items",
	"GET /status/{code}",
}

const (
	// Bound header reads without timing out idle keep-alive connections, which
	// Shutdown closes.
	readHeaderTimeout = 10 * time.Second

	// Leave enough time for the driver to report a shutdown error before its
	// own process timeout expires.
	shutdownTimeout = 10 * time.Second
)

// RunServer hosts the shared HTTP exchanges until the driver says stop.
//
// The external driver prevents client spans in this server run. Closing stdin
// stops the server and gives the SDK a chance to flush.
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
		// Return immediately if Serve fails; waiting for stdin would leave the
		// process hung until the driver's timeout.
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
