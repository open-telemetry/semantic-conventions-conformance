# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""GenAI span name policy: registry span name templates, and the fallback."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from genai_conformance import DOMAIN
from opentelemetry.conformance import WeaverNotInstalledError, check_weaver

_POLICIES = Path(__file__).parents[1] / "src/genai_conformance/policies"


def _template(pattern: str) -> dict[str, Any]:
    """A template as weaver resolves it: the pattern split into parts."""
    parts: list[dict[str, str]] = []
    for i, piece in enumerate(re.split(r"\{([^}]+)\}", pattern)):
        if i % 2:
            parts.append({"type": "attribute", "attribute": piece})
        elif piece:
            parts.append({"type": "literal", "value": piece})
    return {
        "pattern": pattern,
        "attributes": [p["attribute"] for p in parts if p["type"] == "attribute"],
        "parts": parts,
    }


def _model(*, templates: bool) -> dict[str, Any]:
    def span(kind: str, *patterns: str) -> dict[str, Any]:
        definition: dict[str, Any] = {"kind": kind, "attributes": {}}
        if templates:
            definition["name_templates"] = [_template(p) for p in patterns]
        return definition

    return {
        "spans": {
            "gen_ai.client.inference": span(
                "client",
                "{gen_ai.operation.name} {gen_ai.request.model}",
                "{gen_ai.operation.name}",
            ),
            "gen_ai.execute_tool.internal": span(
                "internal", "execute_tool {gen_ai.tool.name}"
            ),
            "gen_ai.execute_tool.load_skill.internal": span(
                "internal",
                "execute_tool {gen_ai.tool.name} {gen_ai.skill.name}",
                "execute_tool {gen_ai.tool.name}",
            ),
        },
        # Not an enum in the real registry; declared one here to cover `_OTHER`.
        "enums": {
            "gen_ai.operation.name": ["chat", "execute_tool"],
            "gen_ai.request.model": ["gpt-4", "_OTHER"],
        },
    }


def _span(name: str, kind: str, attributes: dict[str, object]) -> dict[str, Any]:
    return {
        "span": {
            "name": name,
            "kind": kind,
            "attributes": [
                {"name": key, "value": value} for key, value in attributes.items()
            ],
        }
    }


def _tool(name: str, tool: str, skill: str | None = None) -> dict[str, Any]:
    attributes: dict[str, object] = {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": tool,
    }
    if skill is not None:
        attributes["gen_ai.skill.name"] = skill
    return _span(name, "internal", attributes)


def _chat(name: str, model: str) -> dict[str, Any]:
    return _span(
        name,
        "client",
        {"gen_ai.operation.name": "chat", "gen_ai.request.model": model},
    )


_SAMPLES = [
    _tool("execute_tool load_skill my-skill", "load_skill", "my-skill"),
    _tool("execute_tool load_skill", "load_skill", "my-skill"),
    _tool("execute_tool get_weather", "get_weather"),
    _chat("chat", "_OTHER"),
    _chat("chat _OTHER", "_OTHER"),
]


def _name_findings(
    root: Path, model: dict[str, Any]
) -> dict[str, dict[str, Any] | None]:
    """Span name -> the ``genai_span_name_format`` context, if reported."""
    try:
        check_weaver()
        registry = DOMAIN.registry
    except (WeaverNotInstalledError, OSError, RuntimeError) as error:
        pytest.skip(f"GenAI policy test unavailable: {error}")

    (root / "data").mkdir()
    (root / "data/coverage-model.json").write_text(json.dumps(model), encoding="utf-8")
    input_path = root / "input.json"
    input_path.write_text(json.dumps(_SAMPLES), encoding="utf-8")
    report_dir = root / "report"

    result = subprocess.run(
        [
            "weaver",
            "registry",
            "live-check",
            "--quiet",
            "--registry",
            str(registry),
            "--input-source",
            str(input_path),
            "--advice-policies",
            str(_POLICIES),
            "--advice-data",
            str(root / "data/*.json"),
            "--format",
            "json",
            "--fail-on",
            "none",
            "--no-stream",
            "--output",
            str(report_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    report: dict[str, Any] = json.loads(
        (report_dir / "live_check.json").read_text(encoding="utf-8")
    )
    return {
        span["name"]: next(
            (
                advice["context"]
                for advice in span["live_check_result"]["all_advice"]
                if advice["id"] == "genai_span_name_format"
            ),
            None,
        )
        for sample in report["samples"]
        if (span := sample.get("span")) is not None
    }


@pytest.fixture(scope="module")
def with_templates(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, dict[str, Any] | None]:
    return _name_findings(tmp_path_factory.mktemp("templates"), _model(templates=True))


@pytest.fixture(scope="module")
def without_templates(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, dict[str, Any] | None]:
    return _name_findings(
        tmp_path_factory.mktemp("no-templates"), _model(templates=False)
    )


def test_refinement_template_name_is_accepted(with_templates) -> None:
    assert with_templates["execute_tool load_skill my-skill"] is None


def test_refinement_attributes_hold_the_span_to_the_refined_name(
    with_templates,
) -> None:
    assert with_templates["execute_tool load_skill"] == {
        "operation": "execute_tool",
        "expected_form": "execute_tool load_skill my-skill",
    }


def test_base_template_name_is_accepted(with_templates) -> None:
    assert with_templates["execute_tool get_weather"] is None


def test_other_enum_value_is_left_out_of_the_name(with_templates) -> None:
    assert with_templates["chat"] is None
    assert with_templates["chat _OTHER"] == {
        "operation": "chat",
        "expected_form": "chat",
    }


def test_without_templates_the_keyed_attribute_form_is_expected(
    without_templates,
) -> None:
    assert without_templates["execute_tool load_skill my-skill"] == {
        "operation": "execute_tool",
        "keyed_attr": "gen_ai.tool.name",
        "expected_form": "execute_tool load_skill",
    }
    assert without_templates["execute_tool get_weather"] is None
