// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package scenario

import (
	"errors"
	"os"
	"strings"
	"testing"
	"testing/iotest"
)

func TestRequire(t *testing.T) {
	const name = "OTEL_CONFORMANCE_TEST_REQUIRED"
	tests := []struct {
		name    string
		value   string
		present bool
		wantErr bool
	}{
		{name: "unset", wantErr: true},
		{name: "empty", present: true, wantErr: true},
		{name: "present", value: "value", present: true},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if test.present {
				t.Setenv(name, test.value)
			} else {
				t.Setenv(name, "")
				if err := os.Unsetenv(name); err != nil {
					t.Fatal(err)
				}
			}

			got, err := Require(name)

			if test.wantErr {
				if err == nil || !strings.Contains(err.Error(), name) {
					t.Errorf("Require(%q) = %q, %v, want an error naming the variable", name, got, err)
				}
			} else if err != nil || got != test.value {
				t.Errorf("Require(%q) = %q, %v, want %q, nil", name, got, err, test.value)
			}
		})
	}
}

func TestWaitForEOF(t *testing.T) {
	if err := WaitForEOF(strings.NewReader("input before EOF")); err != nil {
		t.Errorf("WaitForEOF() returned %v", err)
	}
}

func TestWaitForEOFReturnsReadError(t *testing.T) {
	want := errors.New("read failed")

	err := WaitForEOF(iotest.ErrReader(want))

	if !errors.Is(err, want) {
		t.Errorf("WaitForEOF() returned %v, want %v", err, want)
	}
}
