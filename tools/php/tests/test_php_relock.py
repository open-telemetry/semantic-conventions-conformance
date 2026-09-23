# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Relocking every committed Composer package with the smallest change."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import otel_conformance_php
from otel_conformance_php import lock_projects, relock, relock_command

TRACKED = (
    "scenarios/http/php/guzzle/opentelemetry-guzzle/composer.lock",
    "scenarios/http/php/slim/opentelemetry-slim/composer.lock",
    "tools/http/test-client/php/composer.lock",
    "tools/php/scenario/composer.lock",
)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    for relative in TRACKED:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], Path]]:
    recorded: list[tuple[list[str], Path]] = []

    def call(command: list[str], cwd: Path) -> int:
        recorded.append((command, Path(cwd)))
        return 0

    monkeypatch.setattr(otel_conformance_php.subprocess, "call", call)
    return recorded


def test_projects_are_the_tracked_locks(repository: Path) -> None:
    assert lock_projects(repository) == sorted(
        (repository / relative).parent for relative in TRACKED
    )


def test_only_the_lock_is_rewritten_and_minimally() -> None:
    assert relock_command()[1:] == [
        "update",
        "--no-install",
        "--no-scripts",
        "--minimal-changes",
        "--no-interaction",
        "--no-progress",
    ]


def test_every_package_is_relocked(
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
        return 3

    monkeypatch.setattr(otel_conformance_php.subprocess, "call", call)

    assert relock(repository) == 3
    assert len(seen) == 1


def test_the_subcommand_relocks_the_current_repository(
    repository: Path,
    calls: list[tuple[list[str], Path]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(repository)

    assert otel_conformance_php.main(["relock"]) == 0
    assert len(calls) == 4


def test_outside_a_repository_says_so(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert otel_conformance_php.main(["relock"]) == 1
    assert "git repository" in capsys.readouterr().err
