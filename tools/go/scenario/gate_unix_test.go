// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//go:build unix

package scenario

import (
	"os"
	"path/filepath"
	"syscall"
	"testing"
	"time"
)

func TestWaitAtGateWaitsUntilTheLauncherClosesThePipe(t *testing.T) {
	path := filepath.Join(t.TempDir(), "gate")
	if err := syscall.Mkfifo(path, 0o600); err != nil {
		t.Fatal(err)
	}
	t.Setenv(GateVariable, path)
	closing := make(chan struct{})
	go func() {
		gate, err := os.OpenFile(path, os.O_WRONLY, 0)
		if err != nil {
			t.Error(err)
			return
		}
		time.Sleep(50 * time.Millisecond)
		close(closing)
		_ = gate.Close()
	}()

	err := WaitAtGate()

	if err != nil {
		t.Errorf("WaitAtGate() returned %v", err)
	}
	select {
	case <-closing:
	default:
		t.Error("WaitAtGate() returned before the launcher closed the pipe")
	}
}
