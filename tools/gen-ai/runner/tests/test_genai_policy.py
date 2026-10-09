# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""GenAI span advice policy behavior around MCP compatibility attributes."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from genai_conformance import DOMAIN
from opentelemetry.conformance import WeaverNotInstalledError, check_weaver

_POLICY = (
    Path(__file__).parents[1]
    / "src/genai_conformance/policies/genai_span_validation.rego"
)
_SHAPE_POLICY_IDS = {
    "genai_expected_attribute_missing",
    "genai_span_kind_unexpected",
    "genai_span_name_format",
}


def _span(name: str, kind: str) -> dict[str, Any]:
    return {
        "span": {
            "name": name,
            "kind": kind,
            "attributes": [
                {"name": "mcp.method.name", "value": "tools/call"},
                {"name": "gen_ai.operation.name", "value": "execute_tool"},
                {"name": "gen_ai.tool.name", "value": "get_weather"},
            ],
        }
    }


def _run_policy(
    root: Path,
    registry: Path,
    model: dict[str, Any],
    samples: list[dict[str, Any]],
) -> dict[tuple[str, str], set[str]]:
    input_path = root / "input.json"
    model_path = root / "coverage-model.json"
    report_dir = root / "report"
    input_path.write_text(json.dumps(samples), encoding="utf-8")
    model_path.write_text(json.dumps(model), encoding="utf-8")

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
            str(_POLICY),
            "--advice-data",
            str(model_path),
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
        (span["kind"], span["name"]): {
            advice["id"]
            for advice in span["live_check_result"]["all_advice"]
            if advice["id"] in _SHAPE_POLICY_IDS
        }
        for sample in report["samples"]
        if (span := sample.get("span")) is not None
    }


@pytest.fixture(scope="module")
def policy_advice(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]]:
    try:
        check_weaver()
        registry = DOMAIN.registry
        model = copy.deepcopy(DOMAIN.coverage_model)
    except (WeaverNotInstalledError, OSError, RuntimeError) as error:
        pytest.skip(f"GenAI policy test unavailable: {error}")

    with_mcp = _run_policy(
        tmp_path_factory.mktemp("genai-policy-mcp"),
        registry,
        model,
        [
            _span("tools/call get_weather", "client"),
            _span("tools/call get_weather", "server"),
            _span("wrong get_weather", "internal"),
        ],
    )

    model["spans"].pop("mcp.client", None)
    model["spans"].pop("mcp.server", None)
    without_mcp = _run_policy(
        tmp_path_factory.mktemp("genai-policy-fallback"),
        registry,
        model,
        [_span("tools/call get_weather", "client")],
    )
    return with_mcp, without_mcp


def test_mcp_client_and_server_spans_skip_genai_shape_rules(
    policy_advice: tuple[
        dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]
    ],
) -> None:
    with_mcp, _ = policy_advice

    assert with_mcp[("client", "tools/call get_weather")] == set()
    assert with_mcp[("server", "tools/call get_weather")] == set()


def test_internal_span_with_mcp_attribute_keeps_genai_shape_rules(
    policy_advice: tuple[
        dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]
    ],
) -> None:
    with_mcp, _ = policy_advice

    assert (
        "genai_span_name_format" in with_mcp[("internal", "wrong get_weather")]
    )


def test_missing_mcp_definitions_keep_genai_shape_rules(
    policy_advice: tuple[
        dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]
    ],
) -> None:
    _, without_mcp = policy_advice
    advice = without_mcp[("client", "tools/call get_weather")]

    assert advice == {"genai_span_name_format"}
