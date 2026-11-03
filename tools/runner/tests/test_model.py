# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Resolving a registry into the coverage model used by reductions."""

from __future__ import annotations

import json
import shutil
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


@pytest.mark.skipif(
    shutil.which("weaver") is None, reason="weaver not installed"
)
def test_resolved_model_keeps_span_and_metric_refinements(tmp_path):
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "manifest.yaml").write_text(
        "name: demo\nschema_url: https://example.com/schemas/1.0.0\n"
    )
    (registry / "signals.yaml").write_text(
        """\
file_format: definition/2
attributes:
  - key: demo.name
    type: string
    brief: The tool name.
    stability: development
  - key: demo.skill
    type: string
    brief: The skill name.
    stability: development
spans:
  - type: demo.tool
    name:
      note: Tool execution.
    kind: internal
    brief: Tool execution.
    stability: development
    requirement_level: recommended
    attributes:
      - ref: demo.name
        requirement_level: required
span_refinements:
  - id: demo.tool.skill
    ref: demo.tool
    brief: Skill execution.
    stability: development
    attributes:
      - ref: demo.skill
        requirement_level: required
metrics:
  - name: demo.duration
    instrument: histogram
    unit: s
    brief: Tool duration.
    stability: development
    requirement_level: recommended
    attributes:
      - ref: demo.name
        requirement_level: required
metric_refinements:
  - id: demo.skill.duration
    ref: demo.duration
    brief: Skill duration.
    stability: development
    attributes:
      - ref: demo.skill
        requirement_level: recommended
"""
    )
    output = _model.resolve(registry, tmp_path / "model.json")
    model = _model.load(output)

    for kind, base, refinement in [
        ("spans", "demo.tool", "demo.tool.skill"),
        ("metrics", "demo.duration", "demo.skill.duration"),
    ]:
        assert "demo.skill" not in model[kind][base]["attributes"]
        assert (
            "demo.skill"
            in model[kind][base]["refinements"][refinement]["attributes"]
        )
        assert "demo.skill" in model[kind][refinement]["attributes"]
    assert model["metrics"]["demo.skill.duration"]["name"] == "demo.duration"
