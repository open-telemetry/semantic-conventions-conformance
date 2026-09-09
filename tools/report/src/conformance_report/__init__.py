# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Aggregate committed coverage against the pinned registries."""

from ._aggregate import SCHEMA_VERSION, build, render, signal_coverage
from ._cli import cli
from ._discover import Target, discover

__all__ = [
    "SCHEMA_VERSION",
    "Target",
    "build",
    "cli",
    "discover",
    "render",
    "signal_coverage",
]
