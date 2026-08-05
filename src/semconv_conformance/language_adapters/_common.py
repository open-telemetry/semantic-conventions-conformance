# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared helpers for the per-language adapter modules."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple


class CommandResult(NamedTuple):
    found: bool
    exit_code: int


class UvNotInstalledError(RuntimeError):
    """Raised when uv is required but not installed."""


@dataclass(frozen=True)
class LanguageAdapter:
    """The per-language hook set the runner calls for every scenario.

    Every adapter module under this package returns one of these from its
    ``build_adapter(ctx)`` factory. The callbacks are intentionally loose so
    that languages with very different toolchains can share one runner:
    compiled languages do real work in ``prebuild_scenario`` where
    interpreted ones pass ``noop_prebuild``, and a language is free to
    install into a shared environment or, as Python does, a per-scenario
    virtualenv.
    """

    #: Install `<library>`'s deps for `<ecosystem>` into whatever scope the
    #: language uses (shared env for most; per-scenario venv for python).
    install_dependencies: Callable[[str, str], None]

    #: Compile / build `<library>` ahead of the run when the language needs
    #: it, or ``noop_prebuild`` for interpreted languages. Split out from
    #: ``install_dependencies`` so Weaver's inactivity timer doesn't start
    #: during a long compile.
    prebuild_scenario: Callable[[str], None]

    #: Execute the scenario for `<library>`/`<ecosystem>` under `env`.
    #: Returns ``CommandResult(found=False, ...)`` when the scenario file
    #: doesn't exist so the runner can print a helpful "available scenarios"
    #: list instead of a crash.
    run_scenario: Callable[[str, str, dict[str, str]], CommandResult]

    #: Enumerate every `<library>-<ecosystem>` id this language knows about
    #: for the "usage" / not-found paths.
    list_scenarios: Callable[[], list[str]]


@dataclass(frozen=True)
class AdapterContext:
    """State shared by every language adapter for one conformance domain."""

    domain_dir: Path


def uv_cmd() -> str:
    # `shutil.which` applies PATHEXT, so this resolves `uv.exe` on Windows.
    uv = shutil.which("uv")
    if uv:
        return uv
    raise UvNotInstalledError(
        "uv is required to install Python test dependencies. "
        "Install it and retry: https://docs.astral.sh/uv/getting-started/installation/"
    )


def noop_prebuild(_lib: str) -> None:
    pass


def data_file_list_scenarios(domain_dir: Path, language: str) -> list[str]:
    """List data-file-discovered scenarios for `language` (`<lang>/<lib>/data-<eco>.json`)."""
    from ..locations import iter_scenario_locations

    return [loc.scenario_id for loc in iter_scenario_locations(domain_dir, language=language)]
