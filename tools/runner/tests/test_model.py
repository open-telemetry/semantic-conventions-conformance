# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Resolving a registry into the coverage model used by reductions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

import pytest

from opentelemetry.conformance import _model


def test_resolution_invokes_weaver_without_a_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        generated = Path(command[-1])
        (generated / "coverage-model.json").write_text('{"spans": {}}')
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model, "check_weaver", lambda: None)
    monkeypatch.setattr(_model.subprocess, "run", run)
    registry = tmp_path / "registry"
    output = tmp_path / "cache" / "model.json"

    assert _model.resolve(registry, output) == output
    assert json.loads(output.read_text()) == {"spans": {}}
    assert len(commands) == 1
    assert commands[0][:-1] == [
        "weaver",
        "registry",
        "generate",
        "--quiet",
        "--v2",
        "--registry",
        str(registry),
        "--templates",
        str(_model._TEMPLATES),  # noqa: SLF001
        "coverage-model",
    ]
    assert not Path(commands[0][-1]).exists()


@pytest.mark.parametrize("cache", ["external", "nested", "nested-relative"])
@pytest.mark.parametrize(
    "change",
    [
        lambda registry: (registry / "spans.yaml").write_text("groups: [x]\n"),
        lambda registry: (registry / "metrics.yaml").unlink(),
        lambda registry: (registry / "metrics.yaml").rename(
            registry / "token-metrics.yaml"
        ),
    ],
    ids=["edited", "deleted", "renamed"],
)
def test_a_registry_is_resolved_again_only_when_its_files_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: Callable[[Path], object],
    cache: str,
) -> None:
    runs: list[list[str]] = []

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        runs.append(command)
        (Path(command[-1]) / "coverage-model.json").write_text("{}")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model, "check_weaver", lambda: None)
    monkeypatch.setattr(_model.subprocess, "run", run)
    registry = tmp_path / "model"
    registry.mkdir()
    (registry / "spans.yaml").write_text("groups: []\n")
    (registry / "metrics.yaml").write_text("groups: []\n")
    cache_path = (
        tmp_path / "cache"
        if cache == "external"
        else registry / ".cache" / "semconv"
    )
    monkeypatch.chdir(registry)
    monkeypatch.setenv(
        "SEMCONV_CACHE",
        str(cache_path.relative_to(registry))
        if cache == "nested-relative"
        else str(cache_path),
    )
    if cache == "nested-relative":
        registry = Path(".")

    first = _model.coverage_model_for(registry)
    assert _model.coverage_model_for(registry) == first
    assert len(runs) == 1

    change(registry)

    assert _model.coverage_model_for(registry) != first
    assert len(runs) == 2
