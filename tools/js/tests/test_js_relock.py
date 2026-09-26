# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Regenerating every committed npm lockfile with the smallest change."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import otel_conformance_js
from otel_conformance_js import lock_projects, relock, relock_command

TRACKED = (
    "scenarios/http/js/package-lock.json",
    "tools/http/test-client/js/package-lock.json",
    # A manifest without a lockfile of its own is not a project to relock.
    "tools/js/scenario-sdk/package.json",
    # Only scenarios/ and tools/ are searched.
    "elsewhere/package-lock.json",
)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    for relative in TRACKED:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    # Untracked: a lockfile git does not know about is not the build's.
    untracked = tmp_path / "scenarios" / "scratch" / "package-lock.json"
    untracked.parent.mkdir(parents=True)
    untracked.write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], Path]]:
    recorded: list[tuple[list[str], Path]] = []

    def call(command: list[str], cwd: Path) -> int:
        recorded.append((command, Path(cwd)))
        return 0

    monkeypatch.setattr(otel_conformance_js.subprocess, "call", call)
    return recorded


def test_projects_are_the_tracked_lockfiles(repository: Path) -> None:
    assert lock_projects(repository) == [
        repository / "scenarios" / "http" / "js",
        repository / "tools" / "http" / "test-client" / "js",
    ]


def test_the_lock_is_rewritten_without_installing_or_running_scripts() -> (
    None
):
    command = relock_command()

    assert command[1:] == [
        "install",
        "--package-lock-only",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
    ]


def test_every_project_is_relocked(
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
        return 7

    monkeypatch.setattr(otel_conformance_js.subprocess, "call", call)

    assert relock(repository) == 7
    assert len(seen) == 1


def test_the_subcommand_relocks_the_current_repository(
    repository: Path,
    calls: list[tuple[list[str], Path]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(repository / "scenarios" / "http" / "js")

    assert otel_conformance_js.main(["relock"]) == 0
    assert len(calls) == 2


def test_outside_a_repository_says_so(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert otel_conformance_js.main(["relock"]) == 1
    assert "git repository" in capsys.readouterr().err
