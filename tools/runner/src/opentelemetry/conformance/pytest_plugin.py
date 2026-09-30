# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Collect ``conformance.yaml`` as one atomic package test.

A scenario directory already says everything a test needs — how to run each
program and what it must produce — so pytest collects the YAML directly rather
than each repo writing a module to point at it. Keeping every scenario in one
item prevents xdist from splitting one package lifecycle across workers.

The session is opened once per directory and closed when the run ends, which
is what lets a complete run write its data file. Which session — which
registry, server and reduction — comes from the ``runner:`` key the directory
declares.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from ._registry import WeaverNotInstalledError, check_weaver
from ._runners import resolve as resolve_runner
from ._spec import SPEC_FILE, SpecError, load_spec

if TYPE_CHECKING:
    from ._session import ConformanceSession, SessionFactory
    from ._spec import PackageSpec

_SESSIONS = pytest.StashKey[dict[Path, "ConformanceSession"]]()
_SPECS = pytest.StashKey[dict[Path, "PackageSpec"]]()
_STACK = pytest.StashKey[ExitStack]()


def pytest_configure(config: pytest.Config) -> None:
    config.stash[_SESSIONS] = {}
    config.stash[_SPECS] = {}
    config.stash[_STACK] = ExitStack()


def pytest_unconfigure(config: pytest.Config) -> None:
    # Closing writes each session's data file, which must happen even when the
    # run failed. A session whose own finalize failed reported that through the
    # item that ran it, so closing only releases what it still holds — the run
    # ends on the failure that was collected, not on a second copy of it
    # raised from here.
    stack = config.stash.get(_STACK, None)
    if stack is None:
        return
    del config.stash[_STACK]
    stack.close()


def pytest_collect_file(
    file_path: Path, parent: pytest.Collector
) -> pytest.Collector | None:
    if file_path.name != SPEC_FILE:
        return None
    return ConformanceFile.from_parent(  # pyright: ignore[reportUnknownMemberType]
        parent, path=file_path
    )


class ConformanceFile(pytest.File):
    """One scenario directory collected as one package test."""

    def collect(self) -> Any:
        try:
            spec = load_spec(self.path.parent)
        except SpecError as error:
            raise pytest.Collector.CollectError(str(error)) from error
        self.config.stash[_SPECS][self.path.parent] = spec
        yield ConformanceItem.from_parent(  # pyright: ignore[reportUnknownMemberType]
            self, name="package"
        )


class ConformanceItem(pytest.Item):
    """Every scenario in one package-scoped live-check."""

    def runtest(self) -> None:
        session = _session_for(self.config, self.path.parent)
        session.run_all()
        package = session.finalize()
        problems = [
            f"{report.name}:\n" + "\n".join(report.failures)
            for report in package.scenarios
            if report.failures
        ]
        live_check_problems = package.failures + package.violations
        if live_check_problems:
            problems.append(
                "package live-check:\n" + "\n".join(live_check_problems)
            )
        if problems:
            raise ConformanceFailure("\n\n".join(problems))

    def repr_failure(self, excinfo: Any, style: Any = None) -> str:
        if isinstance(excinfo.value, ConformanceFailure):
            return str(excinfo.value)
        # The base returns a rich representation; the caller only wants
        # something to print.
        return str(super().repr_failure(excinfo, style))

    def reportinfo(self) -> tuple[Path, int, str]:
        return self.path, 0, self.name


class ConformanceFailure(Exception):
    """What a scenario got wrong, already formatted by the runner."""


def _session_for(config: pytest.Config, directory: Path) -> ConformanceSession:
    """Open the package session collected for ``directory``."""
    sessions = config.stash[_SESSIONS]
    if directory in sessions:
        return sessions[directory]

    try:
        check_weaver()
    except WeaverNotInstalledError as error:
        pytest.skip(str(error))

    specs = config.stash[_SPECS]
    spec = specs.get(directory)
    if spec is None:
        spec = load_spec(directory)
        specs[directory] = spec
    factory: SessionFactory = resolve_runner(directory, spec=spec)
    session = config.stash[_STACK].enter_context(factory(directory, spec=spec))
    sessions[directory] = session
    return session
