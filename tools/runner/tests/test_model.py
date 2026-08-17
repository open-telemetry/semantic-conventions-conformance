# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Resolving a registry into the coverage model used by reductions."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

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
