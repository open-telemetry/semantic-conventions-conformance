// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package scenarios

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"

	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
	httpcontract "github.com/open-telemetry/semantic-conventions-conformance/tools/http/test-client/go"
)

// Transport wraps the round tripper a client scenario sends through, which is
// where a net/http client instrumentation attaches.
type Transport func(http.RoundTripper) http.RoundTripper

// RunClient sends the shared request contract through a net/http client.
//
// The mock server it calls is started by the runner and answers the same
// exchanges a server scenario would, so both sides are measured against
// identical traffic.
func RunClient(transport Transport) error {
	if transport == nil {
		transport = func(base http.RoundTripper) http.RoundTripper { return base }
	}

	baseURL, err := scenario.Require("MOCK_SERVER_URL")
	if err != nil {
		return err
	}

	client := &http.Client{Transport: transport(http.DefaultTransport)}
	return httpcontract.Drive(baseURL, func(method, url, body string) (httpcontract.Response, error) {
		return send(client, method, url, body)
	})
}

func send(
	client *http.Client, method, url, body string,
) (httpcontract.Response, error) {
	var payload io.Reader
	if body != "" {
		payload = strings.NewReader(body)
	}
	request, err := http.NewRequestWithContext(context.Background(), method, url, payload)
	if err != nil {
		return httpcontract.Response{}, err
	}
	request.Header.Set("User-Agent", httpcontract.UserAgent)
	if body != "" {
		request.Header.Set("Content-Type", httpcontract.ContentType)
	}

	response, err := client.Do(request)
	if err != nil {
		return httpcontract.Response{}, err
	}
	defer func() { _ = response.Body.Close() }()

	// Read to the end before returning: a client instrumentation ends its span
	// when the body is drained and closed, so an early return would report a
	// request that never finished.
	answered, err := io.ReadAll(response.Body)
	if err != nil {
		return httpcontract.Response{}, fmt.Errorf("reading the response body: %w", err)
	}
	return httpcontract.Response{StatusCode: response.StatusCode, Body: string(answered)}, nil
}
