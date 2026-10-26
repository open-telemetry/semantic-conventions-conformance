# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Which ecosystems a Renovate PR's lock files are regenerated for.

Reads the PR's changed paths, one per line, on standard input, and prints the
``relock`` job's matrix: ``{"include":[{"ecosystem":"js"},…]}``, or nothing
when no lock file could have gone stale.

Standard library only and run by file path, not as ``-m``: the Runner's
``discover-scenarios`` job has only the runner image's ``python3``, and
importing this package would import the whole runner.
"""

from __future__ import annotations

import json
import sys
from typing import Iterable

ECOSYSTEMS = ("js", "go", "python", "ruby", "php")

# The workflow that sets up every toolchain: a change there can change what
# any lock file resolves to.
ALL = frozenset({".github/workflows/runner.yml"})

MANIFESTS = {
    "package.json": "js",
    "package-lock.json": "js",
    "go.mod": "go",
    "go.sum": "go",
    "pyproject.toml": "python",
    "uv.lock": "python",
    "Gemfile": "ruby",
    "Gemfile.lock": "ruby",
    "composer.json": "php",
    "composer.lock": "php",
}


def ecosystems(paths: Iterable[str]) -> list[str]:
    """The ecosystems whose lock files ``paths`` could have made stale."""
    found: set[str] = set()
    for path in paths:
        if path in ALL:
            return list(ECOSYSTEMS)
        name = path.rsplit("/", 1)[-1]
        if name.endswith(".gemspec"):
            found.add("ruby")
        elif name in MANIFESTS:
            found.add(MANIFESTS[name])
    return [ecosystem for ecosystem in ECOSYSTEMS if ecosystem in found]


def matrix(paths: Iterable[str]) -> str:
    """The ``relock`` job's matrix, or ``""`` when there is nothing to do."""
    found = ecosystems(paths)
    if not found:
        return ""
    include = [{"ecosystem": ecosystem} for ecosystem in found]
    return json.dumps({"include": include}, separators=(",", ":"))


def main() -> int:
    paths = [line.strip() for line in sys.stdin if line.strip()]
    print(matrix(paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
