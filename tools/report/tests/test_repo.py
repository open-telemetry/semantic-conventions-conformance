# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The report this repo actually produces, read as the site reads it.

These assert invariants of the report alone, never a comparison against the
scenario tree. `.github/workflows/report.yml` rebuilds the report nightly, so
between a scenario landing on main and that rebuild the two are legitimately
out of step, and a test that compared them would fail unrelated pull requests.

Tree-derived properties belong to the unit tests, which build their own
fixtures: `test_discover` for which directories become targets, and
`test_aggregate` for what a target carries.

Skipped when the committed report is absent, because rebuilding it needs weaver
and a fetched registry.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conformance_report._aggregate import GENERATED_BY

ROOT = Path(__file__).parents[3]
REPORT = ROOT / "docs" / "data" / "conformance.json"

pytestmark = pytest.mark.skipif(
    not REPORT.is_file(), reason="docs/data/conformance.json is not built"
)


@pytest.fixture(scope="module")
def report() -> dict[str, object]:
    return json.loads(REPORT.read_text(encoding="utf-8"))


def targets(report: dict[str, object]) -> list[dict[str, object]]:
    found = report["targets"]
    assert isinstance(found, list)
    return found


def test_the_domain_and_language_are_the_ones_the_path_names(
    report: dict[str, object],
) -> None:
    """The facets are path-derived, and nothing else in the tree says them.

    A `data.json` names its runner, and one runner spans four languages, so a
    target whose language does not match its directory is one the site would
    colour and group wrong.
    """
    for target in targets(report):
        domain, language, *rest = str(target["id"]).split("/")
        assert target["domain"] == domain
        assert target["language"] == language
        assert target["side"] in (None, rest[-1])


def test_the_finding_count_agrees_with_the_findings(
    report: dict[str, object],
) -> None:
    """The count the site sorts on agrees with the list it counts.

    That findings reach the report unaltered is
    `test_aggregate.test_findings_pass_through_verbatim`. Here it is only the
    denormalised count that could drift.
    """
    for target in targets(report):
        assert target["summary"]["findings"] == len(target["findings"])


def test_a_fully_conforming_target_is_not_scored_down_for_opt_ins(
    report: dict[str, object],
) -> None:
    """The reason there is no blended score.

    okhttp through the java agent carries every required and every recommended
    attribute on its span, and none of the eleven opt-ins, which is correct
    behaviour. A single percentage over all five levels would rank it around
    40% and read as a failing implementation.
    """
    (found,) = [
        t
        for t in targets(report)
        if t["id"] == "http/java/okhttp/opentelemetry-javaagent/client"
    ]
    (span,) = [s for s in found["signals"] if s["name"] == "http.client"]
    coverage = span["coverage"]
    for level in ("required", "recommended"):
        assert coverage[level]["emitted"] == coverage[level]["declared"] > 0
    assert coverage["opt_in"]["emitted"] == 0
    assert coverage["opt_in"]["declared"] > coverage["required"]["declared"]
    assert found["summary"]["findings"] == 0


def test_competing_implementations_of_one_library_are_distinguishable(
    report: dict[str, object],
) -> None:
    """The comparison the repo exists to make.

    Three instrumentations exercise the openai client directly, and two of them
    have coordinates that shorten to the same word: OpenLLMetry publishes
    `opentelemetry-instrumentation-openai` and OpenTelemetry's own is
    `opentelemetry-instrumentation-genai-openai`. So the label has to come from
    the tree rather than from the package name.

    A fourth reaches OpenAI through langchain and declares `langchain-openai`
    as what it instruments, which is why it is not in this list.
    """
    labels = sorted(
        t["label"]
        for t in targets(report)
        if t["instrumented_library"] == "openai"
    )
    assert labels == ["openinference", "openllmetry", "opentelemetry-openai"]

    coordinates = {
        t["instrumentation_library"]
        for t in targets(report)
        if t["instrumented_library"] == "openai"
    }
    assert "opentelemetry-instrumentation-openai" in coordinates
    assert "opentelemetry-instrumentation-genai-openai" in coordinates


def test_the_registry_slice_covers_every_signal_a_target_emitted(
    report: dict[str, object],
) -> None:
    """A signal with no declaration shipped would score as unknown on the site."""
    registry = report["registry"]
    unresolved = [
        (t["id"], s["name"])
        for t in targets(report)
        for s in t["signals"]
        if s.get("declared", "present") is None
    ]
    assert unresolved == []
    for target in targets(report):
        for signal in target["signals"]:
            declared = registry[target["runner"]][f"{signal['type']}s"]
            assert signal["name"] in declared


def test_the_report_carries_no_timestamp(report: dict[str, object]) -> None:
    """Anything per-run would open a nightly pull request saying nothing."""
    text = REPORT.read_text(encoding="utf-8").lower()
    for word in ("timestamp", "generated_at", '"date"', "built_at"):
        assert word not in text


def test_the_report_says_what_generates_it(report: dict[str, object]) -> None:
    """The marker that tells a reader not to edit the file by hand."""
    assert report["generated_by"] == GENERATED_BY
