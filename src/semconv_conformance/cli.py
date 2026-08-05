# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared factories for console-script entry points."""

from __future__ import annotations

from collections.abc import Callable

from semconv_conformance.runner import DomainConfig, run_main


def make_run_scenario_entrypoint(config: DomainConfig) -> Callable[[], int]:
    """Return a run-scenario CLI entrypoint bound to one domain config."""

    def main() -> int:
        return run_main(config)

    return main
