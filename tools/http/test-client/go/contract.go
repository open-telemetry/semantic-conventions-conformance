// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package httpcontract is the HTTP conformance exchanges, as Go reads them.
//
// The traffic is written down once, in tools/http/test-client/contract.yaml,
// so a Go scenario and a scenario in any other language are measured against
// the same requests and their coverage files stay comparable. Every Go
// framework shares this package rather than restating the answers, while
// server scenarios declare their routes in their framework's native form.
package httpcontract

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"

	"go.yaml.in/yaml/v3"
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

// ScenarioIndexVariable names the zero-based contract entry selected by the
// runner for this process.
const ScenarioIndexVariable = "OTEL_CONFORMANCE_SCENARIO_INDEX"

// checkoutPath is where the contract sits in a checkout, searched for upwards
// from the working directory — which the runner sets to the scenario
// directory, and `go test` to the package's own.
const checkoutPath = "tools/http/test-client/contract.yaml"

// Exchange is one concrete request and the answer the contract requires.
//
// Body is empty for a request that carries none. The only substitution in
// ResponseBody is the literal ${requestBody}, for the body that arrived.
type Exchange struct {
	Method       string
	Path         string
	Body         string
	Status       int
	ResponseBody string
	Readiness    bool
	Description  string
}

// RenderResponseBody is the response body with the request body inserted.
func (e Exchange) RenderResponseBody(requestBody string) string {
	if requestBody == "" {
		requestBody = "{}"
	}
	return strings.ReplaceAll(e.ResponseBody, "${requestBody}", requestBody)
}

// Response is the status and body returned by a request or route.
type Response struct {
	StatusCode int
	Body       string
}

// Error reports a contract validation failure.
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
	Readiness entry   `yaml:"readiness"`
	Scenarios []entry `yaml:"scenarios"`
}

type entry struct {
	Description string `yaml:"description"`
	Action      action `yaml:"action"`
}

type action struct {
	Request  request  `yaml:"request"`
	Response response `yaml:"response"`
}

type request struct {
	Method string `yaml:"method"`
	Path   string `yaml:"path"`
	Body   string `yaml:"body"`
}

type response struct {
	Status int    `yaml:"status"`
	Body   string `yaml:"body"`
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
	return exchanges[1:], nil
}

// ScenarioRequest is the one request selected by the runner's zero-based
// contract index.
func ScenarioRequest() (Exchange, error) {
	raw, ok := os.LookupEnv(ScenarioIndexVariable)
	if !ok {
		return Exchange{}, fmt.Errorf("%s is not set", ScenarioIndexVariable)
	}
	index, err := strconv.Atoi(raw)
	if err != nil || index < 0 || strconv.Itoa(index) != raw {
		return Exchange{}, fmt.Errorf(
			"%s must be a zero-based decimal index, got %q", ScenarioIndexVariable, raw)
	}
	requests, err := Requests()
	if err != nil {
		return Exchange{}, err
	}
	if index >= len(requests) {
		return Exchange{}, fmt.Errorf(
			"%s=%d selects no contract entry; expected 0..%d",
			ScenarioIndexVariable, index, len(requests)-1)
	}
	return requests[index], nil
}

// Lookup is the exchange answering "method path", if the contract describes
// one. It returns an error when the contract cannot be loaded.
func Lookup(method, path string) (Exchange, bool, error) {
	exchanges, err := Exchanges()
	if err != nil {
		return Exchange{}, false, err
	}
	for _, exchange := range exchanges {
		if exchange.Method == method && exchange.Path == path {
			return exchange, true, nil
		}
	}
	pathWithoutQuery := withoutQuery(path)
	for _, exchange := range exchanges {
		if exchange.Method == method && withoutQuery(exchange.Path) == pathWithoutQuery {
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
	if err := yaml.Unmarshal(raw, &parsed); err != nil {
		return nil, fmt.Errorf("could not parse %s: %w", path, err)
	}
	if len(parsed.Scenarios) == 0 {
		return nil, fmt.Errorf("%s describes no requests", path)
	}
	exchanges := make([]Exchange, 0, len(parsed.Scenarios)+1)
	exchanges = append(exchanges, parsed.Readiness.exchange(true))
	for _, scenario := range parsed.Scenarios {
		exchanges = append(exchanges, scenario.exchange(false))
	}
	return exchanges, nil
}

func (e entry) exchange(readiness bool) Exchange {
	return Exchange{
		Method:       e.Action.Request.Method,
		Path:         e.Action.Request.Path,
		Body:         e.Action.Request.Body,
		Status:       e.Action.Response.Status,
		ResponseBody: e.Action.Response.Body,
		Readiness:    readiness,
		Description:  e.Description,
	}
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
