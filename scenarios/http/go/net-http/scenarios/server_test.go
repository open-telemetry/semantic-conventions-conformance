// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package scenarios

import (
	"net/http/httptest"
	"testing"
)

func TestRequestTargetIncludesTheQuery(t *testing.T) {
	request := httptest.NewRequest(
		"GET",
		"http://example.test/users/123?fields=name&verbose=true",
		nil,
	)

	got := requestTarget(request)
	want := "/users/123?fields=name&verbose=true"
	if got != want {
		t.Errorf("requestTarget() = %q, want %q", got, want)
	}
}
