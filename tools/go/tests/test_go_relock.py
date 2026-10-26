# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Tidying every committed Go module, the ones others replace first."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import otel_conformance_go
from otel_conformance_go import lock_projects, relock, relock_command

TRACKED = (
    "scenarios/http/go/go.mod",
    "tools/go/go.mod",
    "tools/http/test-client/go/go.mod",
    "elsewhere/go.mod",
)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    for relative in TRACKED:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("module example\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], Path]]:
    recorded: list[tuple[list[str], Path]] = []

    def call(command: list[str], cwd: Path) -> int:
        recorded.append((command, Path(cwd)))
        return 0

    monkeypatch.setattr(otel_conformance_go.subprocess, "call", call)
    return recorded


def test_modules_under_tools_come_first(repository: Path) -> None:
    """scenarios/http/go replaces the tools/ modules: tidy those first."""
    assert lock_projects(repository) == [
        repository / "tools" / "go",
        repository / "tools" / "http" / "test-client" / "go",
        repository / "scenarios" / "http" / "go",
    ]


def test_the_module_is_tidied() -> None:
    assert relock_command() == ["go", "mod", "tidy"]


def test_every_module_is_tidied_in_order(
    repository: Path, calls: list[tuple[list[str], Path]]
) -> None:
    assert relock(repository) == 0
    assert [cwd for _, cwd in calls] == lock_projects(repository)


def test_the_first_failure_stops_the_run(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Path] = []

    def call(command: list[str], cwd: Path) -> int:
        seen.append(Path(cwd))
        return 1

    monkeypatch.setattr(otel_conformance_go.subprocess, "call", call)

    assert relock(repository) == 1
    assert seen == [repository / "tools" / "go"]


def test_relock_needs_no_module_around_it(
    repository: Path,
    calls: list[tuple[list[str], Path]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unlike build and run, relock works from anywhere in the repository."""
    monkeypatch.chdir(repository)

    assert otel_conformance_go.main(["relock"]) == 0
    assert len(calls) == 3


def test_outside_a_repository_says_so(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert otel_conformance_go.main(["relock"]) == 1
    assert "git repository" in capsys.readouterr().err
