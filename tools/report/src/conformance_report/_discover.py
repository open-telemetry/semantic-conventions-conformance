# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Every conformance directory in a checkout, with what it declared.

Identity comes from the ``conformance.yaml`` beside the data — except the
language, which nothing declares (``runner:`` names the domain, and one domain
spans four languages). So the layout is a contract of the *reporting* layer
rather than of the runner::

    scenarios/<domain>/<language>/<library>/<instrumentation>[/<side>]
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from opentelemetry.conformance import PackageSpec, load_spec

SPEC_FILE = "conformance.yaml"
DATA_FILE = "data.json"
SCENARIO_ROOT = "scenarios"

# HTTP gives each side its own directory: coverage reduces everything a package
# emitted, so a server run must not be able to hide a client span.
_SIDES = ("client", "server")

# A checkout that has run the scenarios holds an interpreter, a package tree
# and build output inside the very directories being walked, and a `data.json`
# or `conformance.yaml` in one of those belongs to a dependency rather than to
# this repo. Pruned rather than filtered afterwards, so the walk does not
# descend into a `node_modules` at all.
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
    """Every file called ``name`` under ``scenarios``, top-down.

    ``Path.rglob`` would also return the ones a dependency or a build brought
    into the tree; see :data:`_NOT_SOURCE`. Callers that care about the order
    of the whole set sort what comes back.
    """
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
    # Declared, and authoritative over anything the path suggests.
    spec: PackageSpec
    directory: Path

    @property
    def runner(self) -> str | None:
        return self.spec.runner


def _facets(relative: Path) -> tuple[str, str, str, str, str | None]:
    """Split a directory under ``scenarios/`` into the layout above."""
    parts = relative.parts
    if len(parts) < 4:
        raise ValueError(
            f"{relative} is not <domain>/<language>/<library>/"
            "<instrumentation>[/<side>]"
        )
    domain, language, library, instrumentation = parts[:4]
    side = parts[4] if len(parts) > 4 and parts[4] in _SIDES else None
    return domain, language, library, instrumentation, side


def discover(root: Path) -> list[Target]:
    """Every conformance directory under ``root`` that has a reduction.

    A spec with no ``data.json`` was never run to completion. Skipped, rather
    than reported as empty coverage — an absent measurement is not a failing
    implementation.
    """
    scenarios = root / SCENARIO_ROOT
    found: list[Target] = []
    for spec_file in sorted(walk(scenarios, SPEC_FILE)):
        directory = spec_file.parent
        if not (directory / DATA_FILE).is_file():
            continue
        relative = directory.relative_to(scenarios)
        domain, language, library, instrumentation, side = _facets(relative)
        found.append(
            Target(
                id=relative.as_posix(),
                path=directory.relative_to(root).as_posix(),
                domain=domain,
                language=language,
                library=library,
                instrumentation=instrumentation,
                side=side,
                spec=load_spec(directory),
                directory=directory,
            )
        )
    return found
