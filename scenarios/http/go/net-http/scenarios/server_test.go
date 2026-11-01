// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package scenarios

import (
	"testing"

	"github.com/open-telemetry/semantic-conventions-conformance/scenarios/http/go/internal/httpservertest"
)

func TestHandlerAnswersContract(t *testing.T) {
	httpservertest.AssertContract(t, newHandler(nil))
}
