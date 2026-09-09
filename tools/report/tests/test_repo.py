# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Structural checks on the committed report, independent of scenario results."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conformance_report._aggregate import GENERATED_BY, SCHEMA_VERSION
from conformance_report._types import Report

REPORT = Path(__file__).parents[3] / "docs" / "data" / "conformance.json"


@pytest.fixture(scope="module")
def report() -> Report:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_target_ids_are_unique(report: Report) -> None:
    ids = [target["id"] for target in report["targets"]]
    assert len(ids) == len(set(ids))


def test_target_paths_and_facets_agree(report: Report) -> None:
    for target in report["targets"]:
        domain, language, *_ = target["id"].split("/")
        assert target["domain"] == domain
        assert target["language"] == language
        assert target["path"] == f"scenarios/{target['id']}"


def test_summary_agrees_with_signals_and_findings(report: Report) -> None:
    for target in report["targets"]:
        assert target["summary"]["findings"] == len(target["findings"])
        for level in ("required", "recommended"):
            for field in ("emitted", "declared"):
                assert target["summary"][level][field] == sum(
                    signal.get("coverage", {}).get(level, {}).get(field, 0)
                    for signal in target["signals"]
                )


def test_coverage_agrees_with_registry(report: Report) -> None:
    for target in report["targets"]:
        registry = report["registry"][target["runner"]]
        for signal in target["signals"]:
            declaration = registry[f"{signal['type']}s"].get(signal["name"])
            if declaration is None:
                assert signal["declared"] is None
                assert "coverage" not in signal
                continue
            attributes = declaration["attributes"]
            emitted = set(signal["emitted"])
            assert signal["missing"] == sorted(set(attributes) - emitted)
            for level in set(attributes.values()):
                names = {
                    name
                    for name, value in attributes.items()
                    if value == level
                }
                assert signal["coverage"][level] == {
                    "emitted": len(names & emitted),
                    "declared": len(names),
                }


def test_generation_metadata(report: Report) -> None:
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["generated_by"] == GENERATED_BY
    assert set(report) == {
        "schema_version",
        "generated_by",
        "domains",
        "registry",
        "targets",
    }
