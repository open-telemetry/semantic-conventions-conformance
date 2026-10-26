# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Discover measured targets using the layouts documented in README.md."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from opentelemetry.conformance import PackageSpec, load_spec

SPEC_FILE = "conformance.yaml"
DATA_FILE = "data.json"
SCENARIO_ROOT = "scenarios"

_SIDES = ("client", "server")

# Exclude dependencies and build output, which may contain their own specs.
_NOT_SOURCE = frozenset(
    {
        ".git",
        ".gradle",
        ".venv",
        "__pycache__",
        "bin",
        "build",
        "dist",
        "node_modules",
        "obj",
        "out",
        "output",
        "target",
        "venv",
    }
)


def walk(scenarios: Path, name: str) -> Iterator[Path]:
    """Yield files named ``name`` under ``scenarios``, excluding build output."""
    for directory, subdirectories, files in os.walk(scenarios):
        subdirectories[:] = sorted(
            subdirectory
            for subdirectory in subdirectories
            if subdirectory not in _NOT_SOURCE
        )
        if name in files:
            yield Path(directory) / name


@dataclass(frozen=True)
class Target:
    """One conformance directory: where it is, and what it declared."""

    # Path-derived.
    id: str
    path: str
    domain: str
    language: str
    library: str
    instrumentation: str
    side: str | None
    backend: str | None
    # Declared, and authoritative over anything the path suggests.
    spec: PackageSpec
    directory: Path

    @property
    def runner(self) -> str | None:
        return self.spec.runner


def _facets(
    relative: Path,
) -> tuple[str, str, str, str, str | None, str | None]:
    """Return domain, language, library, instrumentation, side and backend."""
    parts = list(relative.parts)
    side = None
    if parts and parts[0] == "http" and parts[-1] in _SIDES:
        side = parts.pop()
    backend = None
    if len(parts) == 5 and parts[0] == "database":
        backend = parts.pop(2)
    if len(parts) != 4 or (parts[0] == "database" and backend is None):
        raise ValueError(
            f"{relative} does not match a supported <domain>/<language>/"
            "layout; see tools/report/README.md"
        )
    domain, language, library, instrumentation = parts
    return domain, language, library, instrumentation, side, backend


def discover(root: Path) -> list[Target]:
    """Return targets under ``root/scenarios`` that have a ``data.json``."""
    scenarios = root / SCENARIO_ROOT
    found: list[Target] = []
    for spec_file in sorted(walk(scenarios, SPEC_FILE)):
        directory = spec_file.parent
        if not (directory / DATA_FILE).is_file():
            continue
        relative = directory.relative_to(scenarios)
        domain, language, library, instrumentation, side, backend = _facets(
            relative
        )
        found.append(
            Target(
                id=relative.as_posix(),
                path=directory.relative_to(root).as_posix(),
                domain=domain,
                language=language,
                library=library,
                instrumentation=instrumentation,
                side=side,
                backend=backend,
                spec=load_spec(directory),
                directory=directory,
            )
        )
    return found
