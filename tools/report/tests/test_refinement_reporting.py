# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Refinement attributes stay visible without changing base scores."""

import pytest

from conformance_report import _aggregate, signal_coverage


@pytest.mark.parametrize(
    "kind, singular", [("spans", "span"), ("metrics", "metric")]
)
def test_refinements_do_not_change_base_scores_or_missing_attributes(
    kind, singular
):
    model = {
        kind: {
            "tool": {
                "attributes": {"tool.name": "required"},
                "refinements": {
                    "tool.load_skill": {
                        "attributes": {"skill.name": "required"},
                    },
                    "tool.command": {
                        "attributes": {"process.exit.code": "recommended"},
                    },
                },
            },
        },
    }
    data = {kind: {"tool": ["tool.name", "skill.name"]}}
    (signal,) = signal_coverage(data, model)

    assert signal["type"] == singular
    assert signal["emitted"] == ["skill.name", "tool.name"]
    assert signal["missing"] == []
    assert signal["coverage"] == {"required": {"emitted": 1, "declared": 1}}
    assert _aggregate._referenced(model, [data])[kind] == model[kind]
