// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Package scenariomain runs instrumented Go scenario commands.
package scenariomain

import (
	"context"
	"errors"
	"log"
	"os"

	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenario"
	"github.com/open-telemetry/semantic-conventions-conformance/tools/go/scenariosdk"
)

// Run initializes the scenario SDK, runs scenario, and flushes telemetry before
// reporting an error and exiting.
func Run(run func() error) {
	if err := runWithSDK(context.Background(), run); err != nil {
		log.Fatal(err)
	}
}

// RunServer runs an instrumented server scenario until the driver closes
// standard input.
func RunServer(run func(stopping <-chan error) error) {
	Run(func() error {
		stopping := make(chan error, 1)
		go func() { stopping <- scenario.WaitForEOF(os.Stdin) }()
		return run(stopping)
	})
}

func runWithSDK(ctx context.Context, run func() error) (err error) {
	sdk, err := scenariosdk.Initialize(ctx)
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, sdk.Shutdown(ctx)) }()

	return run()
}
