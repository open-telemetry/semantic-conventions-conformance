# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Preserving refinement attributes without guessing applicability."""

import pytest

from opentelemetry.conformance._report import Observed
from opentelemetry.conformance._semconv import _reduce


@pytest.mark.parametrize("kind", ["spans", "metrics"])
def test_refinement_attributes_are_kept_without_selecting_a_refinement(kind):
    model = {
        kind: {
            "tool": {
                "attributes": {"tool.name": "required"},
                "refinements": {
                    "tool.load_skill": {
                        "attributes": {"skill.name": "required"},
                    },
                    "tool.command": {
                        "attributes": {
                            "skill.name": "opt_in",
                            "process.exit.code": "recommended",
                        },
                    },
                },
            },
        },
    }
    carried = {
        "tool": {"tool.name", "skill.name", "process.exit.code", "unknown"}
    }
    observed = Observed(**{kind: carried})

    assert _reduce(observed, model)[kind] == {
        "tool": ["process.exit.code", "skill.name", "tool.name"],
    }


def test_explicit_refinement_does_not_pick_up_sibling_attributes():
    model = {
        "spans": {
            "tool.load_skill": {"attributes": {"skill.name": "required"}},
            "tool.command": {"attributes": {"process.exit.code": "required"}},
        },
    }
    observed = Observed(
        spans={"tool.load_skill": {"skill.name", "process.exit.code"}},
    )

    assert _reduce(observed, model)["spans"] == {
        "tool.load_skill": ["skill.name"],
    }


def test_metric_name_matching_refinement_id_does_not_select_it():
    refinement = {"attributes": {"skill.name": "required"}}
    model = {
        "metrics": {
            "tool.duration": {
                "name": "tool.duration",
                "attributes": {"tool.name": "required"},
                "refinements": {"tool.skill.duration": refinement},
            },
            "tool.skill.duration": {
                "name": "tool.duration",
                **refinement,
            },
        },
    }
    observed = Observed(
        metrics={
            "tool.duration": {"tool.name", "skill.name"},
            "tool.skill.duration": {"skill.name"},
        },
    )

    assert _reduce(observed, model)["metrics"] == {
        "tool.duration": ["skill.name", "tool.name"],
    }
