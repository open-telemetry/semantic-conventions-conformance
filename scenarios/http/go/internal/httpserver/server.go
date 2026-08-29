// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package httpserver provides the HTTP-specific process lifecycle and response
// handling shared by Go server scenarios.
package httpserver

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"strconv"
	"time"

	httpcontract "github.com/open-telemetry/semantic-conventions-conformance/tools/http/test-client/go"
)

const (
	// Host is the address every Go HTTP server scenario binds.
	Host = "127.0.0.1"

	readHeaderTimeout = 10 * time.Second
	shutdownTimeout   = 10 * time.Second
)

// Run serves handler until stopping reports that the driver said stop.
func Run(handler http.Handler, stopping <-chan error) error {
	port, err := httpcontract.ScenarioPort()
	if err != nil {
		return err
	}
	if _, err := httpcontract.Exchanges(); err != nil {
		return err
	}

	listener, err := net.Listen("tcp", net.JoinHostPort(Host, strconv.Itoa(port)))
	if err != nil {
		return fmt.Errorf("listening on port %d: %w", port, err)
	}

	server := &http.Server{
		Handler:           handler,
		ReadHeaderTimeout: readHeaderTimeout,
	}
	served := make(chan error, 1)
	go func() { served <- server.Serve(listener) }()

	var stopped error
	select {
	case err := <-served:
		// Serve always returns a non-nil error.
		return err
	case stopped = <-stopping:
	}

	shutdownContext, cancelShutdown := context.WithTimeout(
		context.Background(),
		shutdownTimeout,
	)
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

// Answer writes the contract response for request.
func Answer(writer http.ResponseWriter, request *http.Request) {
	body, err := io.ReadAll(request.Body)
	if err != nil {
		http.Error(writer, err.Error(), http.StatusBadRequest)
		return
	}
	response, err := httpcontract.Respond(
		request.Method,
		request.URL.RequestURI(),
		string(body),
	)
	if err != nil {
		http.Error(writer, err.Error(), http.StatusInternalServerError)
		return
	}
	writer.Header().Set("Content-Type", httpcontract.ContentType)
	writer.WriteHeader(response.StatusCode)
	if _, err := io.WriteString(writer, response.Body); err != nil {
		log.Printf("writing response body: %v", err)
	}
}
