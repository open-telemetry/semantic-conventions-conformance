// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package httpcontract

import (
	"fmt"
	"io"
	"reflect"
	"strings"
)

const progressBodyLimit = 60

// Sender sends one request using the HTTP client library under test. body is
// empty for a request that carries none.
type Sender func(method, url, body string) (Response, error)

// Drive sends the runner-selected request at baseURL through send, checks its
// answer, and writes one progress line to output.
//
// Only a client scenario needs this: it is the sender, so the requests have to
// leave the library under test. A server scenario is driven from outside its
// own process by otel-http-drive and never sends anything.
//
// No health check: the runner starts the mock server a client scenario calls
// and waits for it to answer before running the scenario at all.
func Drive(baseURL string, output io.Writer, send Sender) error {
	if strings.TrimSpace(baseURL) == "" {
		return contractError("base URL must not be blank")
	}
	if output == nil {
		return contractError("output must not be nil")
	}
	if send == nil {
		return contractError("sender must not be nil")
	}
	baseURL = strings.TrimRight(baseURL, "/")
	exchange, err := ScenarioRequest()
	if err != nil {
		return err
	}
	response, err := send(exchange.Method, baseURL+exchange.Path, exchange.Body)
	if err != nil {
		return fmt.Errorf("%s %s: %w", exchange.Method, exchange.Path, err)
	}
	if _, err := fmt.Fprintf(output, "%s %s -> %d %s\n",
		exchange.Method, exchange.Path, response.StatusCode, abbreviate(response.Body)); err != nil {
		return fmt.Errorf("writing result for %s %s: %w",
			exchange.Method, exchange.Path, err)
	}
	return Verify(exchange, response)
}

// Verify checks one answer against the exchange that describes it.
//
// A server answering different traffic from the rest fails the run rather than
// quietly producing a coverage file that cannot be compared with the others.
func Verify(exchange Exchange, response Response) error {
	if response.StatusCode != exchange.Status {
		return contractError(
			"%s %s answered %d, but the contract's request answers %d",
			exchange.Method, exchange.Path, response.StatusCode, exchange.Status)
	}

	// Parsed, not compared as text: whitespace and key order are a language's
	// choice of JSON writer, and neither is part of the contract.
	want, err := parse(exchange.RenderResponseBody(exchange.Body))
	if err != nil {
		return fmt.Errorf("%s %s: %w", exchange.Method, exchange.Path, err)
	}
	got, err := parse(response.Body)
	if err != nil {
		return fmt.Errorf("%s %s: %w", exchange.Method, exchange.Path, err)
	}
	if !reflect.DeepEqual(got, want) {
		return contractError(
			"%s %s answered %v, but the contract's request answers %v",
			exchange.Method, exchange.Path, got, want)
	}
	return nil
}

func abbreviate(value string) string {
	singleLine := strings.NewReplacer("\r", " ", "\n", " ").Replace(value)
	if len(singleLine) <= progressBodyLimit {
		return singleLine
	}
	runes := []rune(singleLine)
	if len(runes) <= progressBodyLimit {
		return singleLine
	}
	return string(runes[:progressBodyLimit])
}
