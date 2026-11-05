// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

//go:build unix

package scenario

import (
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
	"time"
)

func launcherGate(t *testing.T, written string) <-chan struct{} {
	t.Helper()
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
		if written != "" {
			if _, err := gate.WriteString(written); err != nil {
				t.Error(err)
			}
		}
		close(closing)
		_ = gate.Close()
	}()
	return closing
}

func TestWaitAtGateWaitsUntilTheLauncherReleasesIt(t *testing.T) {
	closing := launcherGate(t, GateRelease)

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

func TestWaitAtGateFailsWhenTheLauncherClosesWithoutReleasing(t *testing.T) {
	launcherGate(t, "")

	err := WaitAtGate()

	if err == nil || !strings.Contains(err.Error(), "without releasing") {
		t.Errorf("WaitAtGate() returned %v, want an error that the gate was not released", err)
	}
}

func TestWaitAtGateFailsOnAnythingButTheRelease(t *testing.T) {
	launcherGate(t, "0")

	if err := WaitAtGate(); err == nil {
		t.Error("WaitAtGate() returned nil for a gate closed with the wrong byte")
	}
}

func TestRunSkipsTheWorkloadWhenTheGateIsNotReleased(t *testing.T) {
	launcherGate(t, "")
	ran := false

	err := Run(func() error {
		ran = true
		return nil
	})

	if err == nil || ran {
		t.Errorf("Run() returned %v and ran the workload: %v", err, ran)
	}
}

func TestRunRunsTheWorkloadOnceReleased(t *testing.T) {
	launcherGate(t, GateRelease)
	ran := false

	err := Run(func() error {
		ran = true
		return nil
	})

	if err != nil || !ran {
		t.Errorf("Run() returned %v and ran the workload: %v", err, ran)
	}
}
