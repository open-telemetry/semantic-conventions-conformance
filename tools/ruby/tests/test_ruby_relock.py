# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Relocking every committed bundle, which a frozen bundle would refuse."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

import otel_conformance_ruby
from otel_conformance_ruby import (
    GEMFILE,
    lock_projects,
    relock,
    relock_environment,
)

TRACKED = (
    "scenarios/http/ruby/rack/opentelemetry-instrumentation-rack/server/Gemfile.lock",
    "tools/http/test-client/ruby/Gemfile.lock",
    # A gem without a lock of its own is only ever a path dependency.
    "tools/ruby/scenario-sdk/Gemfile",
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
def tools(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = {
        "ruby": "C:/Ruby/bin/ruby.exe",
        "bundle": "C:/Ruby/bin/bundle.cmd",
    }
    monkeypatch.setattr(otel_conformance_ruby.shutil, "which", paths.get)


@pytest.fixture
def calls(
    monkeypatch: pytest.MonkeyPatch, tools: None
) -> list[dict[str, Any]]:
    recorded: list[dict[str, Any]] = []

    def call(command: list[str], **kwargs: Any) -> int:
        recorded.append({"command": command, **kwargs})
        return 0

    monkeypatch.setattr(otel_conformance_ruby.subprocess, "call", call)
    return recorded


def test_projects_are_the_tracked_locks(repository: Path) -> None:
    assert lock_projects(repository) == [
        repository
        / "scenarios/http/ruby/rack/opentelemetry-instrumentation-rack/server",
        repository / "tools/http/test-client/ruby",
    ]


def test_the_bundle_is_not_frozen_while_relocking(tmp_path: Path) -> None:
    environment = relock_environment(
        tmp_path,
        {"BUNDLE_FROZEN": "true", "BUNDLE_DEPLOYMENT": "true", "KEEP": "1"},
    )

    assert "BUNDLE_FROZEN" not in environment
    assert "BUNDLE_DEPLOYMENT" not in environment
    assert environment["BUNDLE_GEMFILE"] == str(tmp_path / GEMFILE)
    assert environment["BUNDLE_IGNORE_CONFIG"] == "true"
    assert environment["KEEP"] == "1"


def test_every_bundle_is_relocked_without_updating(
    repository: Path, calls: list[dict[str, Any]]
) -> None:
    assert relock(repository) == 0
    assert [call["command"][-1] for call in calls] == ["lock", "lock"]
    assert [Path(call["cwd"]) for call in calls] == lock_projects(repository)


def test_the_first_failure_stops_the_run(
    repository: Path, monkeypatch: pytest.MonkeyPatch, tools: None
) -> None:
    seen: list[Path] = []

    def call(command: list[str], **kwargs: Any) -> int:
        seen.append(Path(kwargs["cwd"]))
        return 5

    monkeypatch.setattr(otel_conformance_ruby.subprocess, "call", call)

    assert relock(repository) == 5
    assert len(seen) == 1


def test_the_subcommand_relocks_the_current_repository(
    repository: Path,
    calls: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(repository)

    assert otel_conformance_ruby.main(["relock"]) == 0
    assert len(calls) == 2


def test_outside_a_repository_says_so(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tools: None,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert otel_conformance_ruby.main(["relock"]) == 1
    assert "git repository" in capsys.readouterr().err
