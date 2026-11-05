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
	"errors"
	"fmt"
	"io"
	"os"
)

// GateVariable names the named pipe a scenario waits at before its workload.
const GateVariable = "OTEL_CONFORMANCE_GATE"

// GateRelease is what the launcher writes to the gate before closing it.
const GateRelease = "1"

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

// WaitAtGate reads the named pipe at [GateVariable] until the launcher
// closes it, and fails unless the launcher wrote [GateRelease] first. It
// returns at once when the variable is unset.
func WaitAtGate() error {
	path := os.Getenv(GateVariable)
	if path == "" {
		return nil
	}
	gate, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("reaching the gate: %w", err)
	}
	defer gate.Close()
	received, err := io.ReadAll(gate)
	if err != nil {
		return fmt.Errorf("waiting at the gate: %w", err)
	}
	if string(received) != GateRelease {
		return errors.New("the launcher closed the gate without releasing it")
	}
	return nil
}

// Serve runs serve until standard input closes.
func Serve(serve func(stopping <-chan error) error) error {
	stopping := make(chan error, 1)
	go func() { stopping <- WaitForEOF(os.Stdin) }()
	return serve(stopping)
}

// Run waits at the gate, then runs workload.
func Run(workload func() error) error {
	if err := WaitAtGate(); err != nil {
		return err
	}
	return workload()
}

// RunServer waits at the gate, then serves until standard input closes.
func RunServer(serve func(stopping <-chan error) error) error {
	return Run(func() error { return Serve(serve) })
}
