// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenario is what a Go scenario needs before any telemetry: what the
// runner told it, and how it learns the runner is finished with it.
//
// It carries no OpenTelemetry dependency at all, which is the point. A
// scenario measuring an out-of-process agent must be able to reach the runner
// and the shutdown protocol without linking an SDK it never asked for, so
// these live apart from [scenariosdk]. Nothing here is specific to a domain.
package scenario

import (
	"fmt"
	"io"
	"os"
)

// Require is the value of name, or a failure naming what was missing.
func Require(name string) (string, error) {
	value := os.Getenv(name)
	if value == "" {
		return "", fmt.Errorf("required environment variable is missing: %s", name)
	}
	return value, nil
}

// WaitForEOF blocks until standard input closes, which is how the driver says
// stop.
//
// A closed pipe rather than a signal: it means the same thing on every
// platform, and returning is what gives an SDK the chance to flush, so a
// scenario that exits any other way reports less than it produced. The
// protocol is the same in every domain.
func WaitForEOF() error {
	// Nothing arrives on standard input; only its close is the signal.
	if _, err := io.Copy(io.Discard, os.Stdin); err != nil {
		return fmt.Errorf("reading standard input: %w", err)
	}
	return nil
}
