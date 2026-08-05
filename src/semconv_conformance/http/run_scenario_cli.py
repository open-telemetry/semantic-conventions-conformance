# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""HTTP run-scenario entry point for console_scripts."""

from __future__ import annotations

from semconv_conformance.http import DOMAIN

main = DOMAIN.run_scenario_main
