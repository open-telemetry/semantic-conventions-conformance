// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package scenariomain

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariosdk"
)

func TestRunWithSDKDoesNotRunScenarioWhenInitializationFails(t *testing.T) {
	t.Setenv(scenariosdk.EndpointVariable, "")
	if err := os.Unsetenv(scenariosdk.EndpointVariable); err != nil {
		t.Fatal(err)
	}
	called := false

	err := runWithSDK(context.Background(), func() error {
		called = true
		return nil
	})

	if called {
		t.Error("runWithSDK() ran the scenario after SDK initialization failed")
	}
	if err == nil || !strings.Contains(err.Error(), scenariosdk.EndpointVariable) {
		t.Errorf(
			"runWithSDK() returned %v, want an error naming %s",
			err,
			scenariosdk.EndpointVariable,
		)
	}
}
