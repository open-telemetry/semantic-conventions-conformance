# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""One report over every committed ``data.json`` in a checkout.

The runner records what one directory emitted. This joins all of them to what
the pinned registries declare, as one committed JSON document. See
``README.md``.
"""

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
