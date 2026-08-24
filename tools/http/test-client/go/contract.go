// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package httpcontract is the HTTP conformance exchanges, as Go reads them.
//
// The traffic is written down once, in tools/http/test-client/contract.json,
// so a Go scenario and a scenario in any other language are measured against
// the same requests and their coverage files stay comparable. Every Go
// framework shares this package rather than restating the answers, while
// server scenarios declare their routes in their framework's native form.
//
// Only the standard library, so importing it next to a scenario drags no
// dependency into a run.
package httpcontract

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// ContentType is what every route answers, so a scenario has one content type
// rather than a rule per route.
const ContentType = "application/json"

// UserAgent is fixed rather than the HTTP library's default, so a server
// scenario sees the same client whichever language sent the requests.
const UserAgent = "otel-http-conformance/1"

// PathVariable names the contract explicitly. //go:embed cannot reach outside
// its own package directory, so the contract is found at run time; this is the
// escape hatch for a binary run away from the checkout it was built in.
const PathVariable = "OTEL_HTTP_CONTRACT"

// checkoutPath is where the contract sits in a checkout, searched for upwards
// from the working directory — which the runner sets to the scenario
// directory, and `go test` to the package's own.
const checkoutPath = "tools/http/test-client/contract.json"

// Exchange is one concrete request and the answer the contract requires.
//
// Body is empty for a request that carries none. The only substitution in
// ResponseBody is the literal ${requestBody}, for the body that arrived.
type Exchange struct {
	Method       string `json:"method"`
	Path         string `json:"path"`
	Body         string `json:"body"`
	Status       int    `json:"status"`
	ResponseBody string `json:"responseBody"`
	Readiness    bool   `json:"readiness"`
	// What the request is in the sequence for — the attribute it should make
	// an instrumentation record. Carried as data rather than as a comment so
	// every language reading the contract has it too.
	Description string `json:"description"`
}

// RenderResponseBody is the response body with the request body inserted.
func (e Exchange) RenderResponseBody(requestBody string) string {
	if requestBody == "" {
		requestBody = "{}"
	}
	return strings.ReplaceAll(e.ResponseBody, "${requestBody}", requestBody)
}

// Response is a status and a body: what a request came back as, and what a
// route answers. One type for both directions, because they are the same pair.
type Response struct {
	StatusCode int
	Body       string
}

// Error is a server answering something the contract does not describe.
type Error struct {
	message string
	cause   error
}

func (e *Error) Error() string { return e.message }

func (e *Error) Unwrap() error { return e.cause }

func contractError(format string, arguments ...any) error {
	return &Error{message: fmt.Sprintf(format, arguments...)}
}

type document struct {
	Requests []Exchange `json:"requests"`
}

// Read once: the contract is a constant for the life of a scenario, and every
// route handler asks for it.
var loaded = sync.OnceValues(load)

// Exchanges is every exchange the contract describes, including readiness, in
// order.
func Exchanges() ([]Exchange, error) {
	return loaded()
}

// Requests is the measured requests to send, in order.
func Requests() ([]Exchange, error) {
	exchanges, err := Exchanges()
	if err != nil {
		return nil, err
	}
	measured := make([]Exchange, 0, len(exchanges))
	for _, exchange := range exchanges {
		if !exchange.Readiness {
			measured = append(measured, exchange)
		}
	}
	return measured, nil
}

// Lookup is the exchange answering "method path", if the contract describes
// one. It returns an error when the contract cannot be loaded.
func Lookup(method, path string) (Exchange, bool, error) {
	exchanges, err := Exchanges()
	if err != nil {
		return Exchange{}, false, err
	}
	path = withoutQuery(path)
	for _, exchange := range exchanges {
		if exchange.Method == method && withoutQuery(exchange.Path) == path {
			return exchange, true, nil
		}
	}
	return Exchange{}, false, nil
}

func withoutQuery(path string) string {
	if query := strings.IndexByte(path, '?'); query != -1 {
		return path[:query]
	}
	return path
}

// parse reads json so two bodies compare by structure rather than by spacing.
func parse(body string) (any, error) {
	var parsed any
	if err := json.Unmarshal([]byte(body), &parsed); err != nil {
		return nil, &Error{
			message: fmt.Sprintf("not JSON: %s: %v", abbreviate(body), err),
			cause:   err,
		}
	}
	return parsed, nil
}

func load() ([]Exchange, error) {
	path, err := locate()
	if err != nil {
		return nil, err
	}
	raw, err := os.ReadFile(path) //nolint:gosec // the local contract path is intentional
	if err != nil {
		return nil, fmt.Errorf("could not read %s: %w", path, err)
	}
	var parsed document
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, fmt.Errorf("could not parse %s: %w", path, err)
	}
	if len(parsed.Requests) == 0 {
		return nil, fmt.Errorf("%s describes no requests", path)
	}
	return parsed.Requests, nil
}

func locate() (string, error) {
	if declared := os.Getenv(PathVariable); declared != "" {
		return declared, nil
	}
	directory, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		candidate := filepath.Join(directory, filepath.FromSlash(checkoutPath))
		if _, err := os.Stat(candidate); err == nil {
			return candidate, nil
		} else if !errors.Is(err, os.ErrNotExist) {
			return "", fmt.Errorf("could not inspect %s: %w", candidate, err)
		}
		parent := filepath.Dir(directory)
		if parent == directory {
			return "", errors.New(
				"no " + checkoutPath + " at or above the working directory — " +
					"set " + PathVariable + " to run away from a checkout")
		}
		directory = parent
	}
}
