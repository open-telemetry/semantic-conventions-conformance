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

// Require returns the environment variable named by name or an error.
func Require(name string) (string, error) {
	value := os.Getenv(name)
	if value == "" {
		return "", fmt.Errorf("required environment variable is missing: %s", name)
	}
	return value, nil
}

// WaitForEOF blocks until input closes.
//
// A closed pipe rather than a signal: it means the same thing on every
// platform, and returning is what gives an SDK the chance to flush, so a
// scenario that exits any other way reports less than it produced. The
// protocol is the same in every domain.
func WaitForEOF(input io.Reader) error {
	if _, err := io.Copy(io.Discard, input); err != nil {
		return fmt.Errorf("reading stop input: %w", err)
	}
	return nil
}
