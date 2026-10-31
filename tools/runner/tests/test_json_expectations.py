# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Nested content expectations through the public YAML parser and checker.

These reports are synthetic Weaver-shaped dicts. They exercise the complete
spec/check path, but do not start Weaver, an SDK, or an OTLP receiver.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from opentelemetry.conformance import SpecError, load_spec
from opentelemetry.conformance._checks import Findings, check

ATTRIBUTE = "gen_ai.input.messages"
PART_TYPES = [{"each": True}, "parts", {"each": True}, "type"]
MISSING = object()


class Report(dict[str, Any]):
    """The dict and violations interface the checker reads from Weaver."""

    def __init__(self, values: list[object]) -> None:
        samples = []
        for value in values:
            attributes = [{"name": "gen_ai.operation.name", "value": "chat"}]
            if value is not MISSING:
                attributes.append({"name": ATTRIBUTE, "value": value})
            samples.append(
                {
                    "span": {
                        "name": "chat synthetic-model",
                        "kind": "client",
                        "attributes": attributes,
                    }
                }
            )
        super().__init__(samples=samples, statistics={})
        self.violations: list[dict[str, object]] = []


def write_spec(directory: Path, matcher: object, *, count: int = 1) -> Path:
    document = {
        "instrumented_library": "synthetic",
        "instrumentation_library": "synthetic-instrumentation",
        "scenarios": {
            "content": {
                "run": "python scenario.py",
                "spans": [
                    {
                        "match": {
                            "attributes": {"gen_ai.operation.name": "chat"}
                        },
                        "expect": {
                            "count": count,
                            "attributes": {ATTRIBUTE: matcher},
                        },
                    }
                ],
            }
        },
    }
    (directory / "conformance.yaml").write_text(
        yaml.safe_dump(document), encoding="utf-8"
    )
    return directory


def findings(
    directory: Path, matcher: object, values: list[object]
) -> Findings:
    spec = load_spec(write_spec(directory, matcher, count=len(values)))
    return check(spec.scenarios["content"], Report(values))


def content(*part_types: str) -> list[dict[str, object]]:
    return [
        {
            "role": "user",
            "parts": [{"type": part_type} for part_type in part_types],
        }
    ]


@pytest.mark.parametrize(
    ("document", "path", "expected"),
    [
        pytest.param(
            content("text", "image"), PART_TYPES, "image", id="image"
        ),
        pytest.param(content("tool_call"), PART_TYPES, "tool_call", id="tool"),
        pytest.param(
            content("tool_call_response"),
            PART_TYPES,
            "tool_call_response",
            id="tool-response",
        ),
        pytest.param(
            content("reasoning", "text"),
            PART_TYPES,
            "reasoning",
            id="reasoning",
        ),
        pytest.param(
            content("text", "image"),
            [0, "parts", 1, "type"],
            "image",
            id="array-index",
        ),
        pytest.param(
            {"*": {"a.b": "image"}},
            ["*", "a.b"],
            "image",
            id="literal-star-and-dot-keys",
        ),
        pytest.param(
            [None, 7, {}, *content("image")],
            PART_TYPES,
            "image",
            id="heterogeneous-array",
        ),
        pytest.param({"value": None}, ["value"], None, id="explicit-null"),
        pytest.param(True, [], True, id="boolean"),
        pytest.param("image", [], "image", id="root-scalar"),
        pytest.param({"value": 1}, ["value"], 1.0, id="json-number"),
    ],
)
def test_json_accepts_selected_scalar(
    tmp_path: Path, document: object, path: list[object], expected: object
) -> None:
    result = findings(
        tmp_path,
        {"json": {"path": path, "contains": expected}},
        [json.dumps(document)],
    )

    assert result.failures == []
    assert result.violations == []


@pytest.mark.parametrize(
    ("document", "path", "expected"),
    [
        pytest.param(content("text"), PART_TYPES, "image", id="dropped-image"),
        pytest.param(
            content("text"), PART_TYPES, "tool_call", id="dropped-tool"
        ),
        pytest.param(
            content("text"), PART_TYPES, "reasoning", id="dropped-reasoning"
        ),
        pytest.param({}, ["value"], None, id="missing-is-not-null"),
        pytest.param([], PART_TYPES, "image", id="empty-selection"),
        pytest.param(
            [{"parts": {"type": "image"}}],
            PART_TYPES,
            "image",
            id="wildcard-is-array-only",
        ),
        pytest.param(
            content("image"),
            [1, "parts", 0, "type"],
            "image",
            id="out-of-range",
        ),
        pytest.param(True, [], 1, id="boolean-is-not-number"),
        pytest.param(1, [], True, id="number-is-not-boolean"),
        pytest.param(1, [], "1", id="number-is-not-string"),
        pytest.param(["image"], [], "image", id="container-is-not-scalar"),
    ],
)
def test_json_rejects_missing_or_different_selected_scalar(
    tmp_path: Path, document: object, path: list[object], expected: object
) -> None:
    result = findings(
        tmp_path,
        {"json": {"path": path, "contains": expected}},
        [json.dumps(document)],
    )

    assert result.failures
    assert result.violations == []


def test_json_requires_content_on_every_matched_span(tmp_path: Path) -> None:
    result = findings(
        tmp_path,
        {"json": {"path": PART_TYPES, "contains": "image"}},
        [json.dumps(content("image")), json.dumps(content("text"))],
    )

    assert result.failures
    assert result.violations == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("9007199254740993.0", 9007199254740992),
        ("1e-4000", 0),
        ("1.0000000000000001", 1),
    ],
)
def test_json_numbers_do_not_match_after_lossy_rounding(
    tmp_path: Path, value: str, expected: int
) -> None:
    result = findings(
        tmp_path, {"json": {"path": [], "contains": expected}}, [value]
    )

    assert result.failures


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.1", 0.1), ("1e2", 100), ("9007199254740993.0", 9007199254740993)],
)
def test_json_numbers_compare_as_decimal_values(
    tmp_path: Path, value: str, expected: int | float
) -> None:
    result = findings(
        tmp_path, {"json": {"path": [], "contains": expected}}, [value]
    )

    assert result.failures == []


@pytest.mark.parametrize(
    ("value", "path", "expected"),
    [
        pytest.param(MISSING, [], None, id="absent-attribute"),
        pytest.param("[", [], "image", id="malformed-json"),
        pytest.param(
            "1e9999999999999999999999999", [], 0, id="unsupported-exponent"
        ),
        pytest.param(
            "[" * 2000 + "0" + "]" * 2000,
            [],
            0,
            id="excessively-nested-json",
        ),
        pytest.param(
            '{"value": "image", "invalid": NaN}',
            ["value"],
            "image",
            id="nan",
        ),
        pytest.param(
            '{"value": "image", "invalid": Infinity}',
            ["value"],
            "image",
            id="infinity",
        ),
        pytest.param(
            '{"value": "image", "invalid": {"nested": NaN}}',
            ["value"],
            "image",
            id="nested-nan",
        ),
        pytest.param(
            {"value": "image"}, ["value"], "image", id="native-object"
        ),
        pytest.param(None, [], None, id="native-null"),
    ],
)
def test_json_rejects_unusable_attribute(
    tmp_path: Path, value: object, path: list[object], expected: object
) -> None:
    result = findings(
        tmp_path, {"json": {"path": path, "contains": expected}}, [value]
    )

    assert result.failures
    assert result.violations == []


@pytest.mark.parametrize("malformed", [False, True])
def test_json_failure_does_not_dump_actual_content(
    tmp_path: Path, malformed: bool
) -> None:
    canary = "private-prompt-canary-4b8e"
    value = json.dumps([{"parts": [{"type": "text", "content": canary}]}])
    if malformed:
        value = value[:-1]
    result = findings(
        tmp_path,
        {"json": {"path": PART_TYPES, "contains": "image"}},
        [value],
    )

    assert result.failures
    assert ATTRIBUTE in "\n".join(result.failures)
    assert canary not in "\n".join(result.failures)


def test_json_does_not_recover_a_weaver_rejected_attribute(
    tmp_path: Path,
) -> None:
    spec = load_spec(
        write_spec(
            tmp_path, {"json": {"path": PART_TYPES, "contains": "image"}}
        )
    )
    report = Report([json.dumps(content("image"))])
    report["samples"][0]["span"]["attributes"][-1]["live_check_result"] = {
        "all_advice": [{"id": "type_mismatch"}]
    }

    result = check(spec.scenarios["content"], report)

    assert len(result.failures) == 1
    assert "missing attribute" in result.failures[0]


def test_json_preserves_zero_span_count_expectations(tmp_path: Path) -> None:
    result = findings(
        tmp_path, {"json": {"path": PART_TYPES, "contains": "image"}}, []
    )

    assert result.failures == []
    assert result.violations == []


@pytest.mark.parametrize(
    "matcher",
    [
        pytest.param(
            {"json": {"path": [], "contains": "image", "unknown": True}},
            id="unknown-json-key",
        ),
        pytest.param(
            {
                "json": {
                    "path": [],
                    "contains": "image",
                    1: True,
                    "extra": True,
                }
            },
            id="mixed-type-unknown-json-keys",
        ),
        pytest.param({"json": {"path": []}}, id="missing-contains"),
        pytest.param(
            {"json": {"path": [], "contains": {"type": "image"}}},
            id="object-contains",
        ),
        pytest.param(
            {"json": {"path": [], "contains": ["image"]}}, id="array-contains"
        ),
        pytest.param(
            {"json": {"path": [], "contains": float("nan")}},
            id="nonfinite-contains",
        ),
        pytest.param({"json": {"contains": "image"}}, id="missing-path"),
        pytest.param(
            {"json": {"path": "$.parts[*].type", "contains": "image"}},
            id="path-is-not-jsonpath-string",
        ),
        pytest.param(
            {"json": {"path": [True], "contains": "image"}},
            id="boolean-index",
        ),
        pytest.param(
            {"json": {"path": [-1], "contains": "image"}}, id="negative-index"
        ),
        pytest.param(
            {"json": {"path": [0.5], "contains": "image"}}, id="float-index"
        ),
        pytest.param(
            {"json": {"path": [{"each": False}], "contains": "image"}},
            id="false-wildcard",
        ),
        pytest.param(
            {"json": {"path": [{"each": 1}], "contains": "image"}},
            id="numeric-wildcard",
        ),
        pytest.param(
            {
                "json": {
                    "path": [{"each": True, "unknown": True}],
                    "contains": "image",
                }
            },
            id="unknown-wildcard-key",
        ),
        pytest.param(
            {"json": {"path": [None], "contains": "image"}},
            id="null-path-segment",
        ),
        pytest.param(
            {"json": {"path": [], "contains": "image"}, "unknown": True},
            id="unknown-matcher-key",
        ),
        pytest.param(
            {"json": {"path": [], "contains": "image"}, "present": True},
            id="mixed-matcher-forms",
        ),
    ],
)
def test_json_invalid_spec_is_rejected(
    tmp_path: Path, matcher: object
) -> None:
    with pytest.raises(SpecError, match="(?i)(json|path|matcher|unknown)"):
        load_spec(write_spec(tmp_path, matcher))


@pytest.mark.parametrize(
    ("matcher", "values"),
    [
        pytest.param("literal", ["literal"], id="literal-equality"),
        pytest.param({"present": True}, ["present"], id="presence"),
        pytest.param({"distinct": 2}, ["first", "second"], id="distinct"),
    ],
)
def test_existing_attribute_matchers_still_pass(
    tmp_path: Path, matcher: object, values: list[object]
) -> None:
    result = findings(tmp_path, matcher, values)

    assert result.failures == []
    assert result.violations == []
