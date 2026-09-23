# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Relocking every committed uv project with the smallest change."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from otel_conformance_python import relock as relock_module
from otel_conformance_python.relock import (
    lock_projects,
    relock,
    relock_command,
)

TRACKED = (
    "scenarios/http/python/flask/opentelemetry-flask/server/uv.lock",
    "scenarios/gen-ai/python/openai/openllmetry/uv.lock",
    "tools/gen-ai/mock-server/uv.lock",
    # A project without a lock is not relocked: it is not run with uv.
    "tools/runner/pyproject.toml",
)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    for relative in TRACKED:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], Path]]:
    recorded: list[tuple[list[str], Path]] = []

    def call(command: list[str], cwd: Path) -> int:
        recorded.append((command, Path(cwd)))
        return 0

    monkeypatch.setattr(relock_module.subprocess, "call", call)
    return recorded


def test_projects_are_the_tracked_locks(repository: Path) -> None:
    assert lock_projects(repository) == [
        repository / "scenarios/gen-ai/python/openai/openllmetry",
        repository / "scenarios/http/python/flask/opentelemetry-flask/server",
        repository / "tools/gen-ai/mock-server",
    ]


def test_the_lock_is_resolved_without_upgrading() -> None:
    """No `--upgrade`: what already resolves keeps its pin."""
    assert relock_command()[1:] == ["lock"]


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
        return 2

    monkeypatch.setattr(relock_module.subprocess, "call", call)

    assert relock(repository) == 2
    assert len(seen) == 1


def test_the_script_relocks_the_current_repository(
    repository: Path,
    calls: list[tuple[list[str], Path]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(repository / "tools")

    assert relock_module.main([]) == 0
    assert len(calls) == 3


def test_outside_a_repository_says_so(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert relock_module.main([]) == 1
    assert "git repository" in capsys.readouterr().err
