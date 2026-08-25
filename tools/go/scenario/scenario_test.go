// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

package scenario

import (
	"errors"
	"strings"
	"testing"
	"testing/iotest"
)

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
