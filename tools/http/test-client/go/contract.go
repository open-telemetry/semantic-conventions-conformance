// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package httpcontract decodes the HTTP conformance actions supplied by the runner.
package httpcontract

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
	"sync"
)

const ContentType = "application/json"
const UserAgent = "otel-http-conformance/1"
const ActionVariable = "OTEL_CONFORMANCE_SCENARIO_ACTION"
const ActionsVariable = "OTEL_CONFORMANCE_SCENARIO_ACTIONS"

type Exchange struct {
	Method       string
	Path         string
	Body         string
	Status       int
	ResponseBody string
	Readiness    bool
	Description  string
}

func (e Exchange) RenderResponseBody(requestBody string) string {
	if requestBody == "" {
		requestBody = "{}"
	}
	return strings.ReplaceAll(e.ResponseBody, "${requestBody}", requestBody)
}

type Response struct {
	StatusCode int
	Body       string
}

type Error struct {
	message string
	cause   error
}

func (e *Error) Error() string { return e.message }
func (e *Error) Unwrap() error { return e.cause }

func contractError(format string, arguments ...any) error {
	return &Error{message: fmt.Sprintf(format, arguments...)}
}

type action struct {
	Request  request  `json:"request"`
	Response response `json:"response"`
}

type request struct {
	Method string  `json:"method"`
	Path   string  `json:"path"`
	Body   *string `json:"body,omitempty"`
}

type response struct {
	Status int     `json:"status"`
	Body   *string `json:"body"`
}

var actionCache struct {
	sync.Mutex
	raw       string
	exchanges []Exchange
}

func Exchanges() ([]Exchange, error) {
	raw, ok := os.LookupEnv(ActionsVariable)
	if !ok {
		return nil, fmt.Errorf("%s is not set", ActionsVariable)
	}
	actionCache.Lock()
	defer actionCache.Unlock()
	if actionCache.exchanges != nil && actionCache.raw == raw {
		return actionCache.exchanges, nil
	}

	var actions []action
	if err := decodeJSON(raw, ActionsVariable, &actions); err != nil {
		return nil, err
	}
	if len(actions) == 0 {
		return nil, fmt.Errorf("%s must be a non-empty JSON array of actions", ActionsVariable)
	}
	exchanges := make([]Exchange, len(actions))
	for index, action := range actions {
		exchange, err := action.exchange(index == 0, fmt.Sprintf("%s[%d]", ActionsVariable, index))
		if err != nil {
			return nil, err
		}
		exchanges[index] = exchange
	}
	actionCache.raw = raw
	actionCache.exchanges = exchanges
	return exchanges, nil
}

func Requests() ([]Exchange, error) {
	exchanges, err := Exchanges()
	if err != nil {
		return nil, err
	}
	return exchanges[1:], nil
}

func ScenarioRequest() (Exchange, error) {
	raw, ok := os.LookupEnv(ActionVariable)
	if !ok {
		return Exchange{}, fmt.Errorf("%s is not set", ActionVariable)
	}
	var selected action
	if err := decodeJSON(raw, ActionVariable, &selected); err != nil {
		return Exchange{}, err
	}
	return selected.exchange(false, ActionVariable)
}

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

func (a action) exchange(readiness bool, where string) (Exchange, error) {
	if a.Request.Method == "" {
		return Exchange{}, fmt.Errorf("%s.request.method must be a non-empty string", where)
	}
	if !strings.HasPrefix(a.Request.Path, "/") {
		return Exchange{}, fmt.Errorf("%s.request.path must start with '/'", where)
	}
	if a.Response.Status < 100 || a.Response.Status > 599 {
		return Exchange{}, fmt.Errorf("%s.response.status must be an HTTP status", where)
	}
	if a.Response.Body == nil {
		return Exchange{}, fmt.Errorf("%s.response.body must be a string", where)
	}
	body := ""
	if a.Request.Body != nil {
		body = *a.Request.Body
	}
	description := "runner action"
	if readiness {
		description = "runner readiness action"
	}
	return Exchange{
		Method:       a.Request.Method,
		Path:         a.Request.Path,
		Body:         body,
		Status:       a.Response.Status,
		ResponseBody: *a.Response.Body,
		Readiness:    readiness,
		Description:  description,
	}, nil
}

func decodeJSON(raw, variable string, target any) error {
	decoder := json.NewDecoder(strings.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return fmt.Errorf("%s contains malformed JSON: %w", variable, err)
	}
	if err := decoder.Decode(new(any)); err != io.EOF {
		if err == nil {
			return fmt.Errorf("%s contains more than one JSON value", variable)
		}
		return fmt.Errorf("%s contains malformed JSON: %w", variable, err)
	}
	return nil
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
