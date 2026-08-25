# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Reading weaver reports, and reducing them against a coverage model.

Both halves of the registry-shaped reduction: what ``_report`` sees in a run,
and what ``_semconv`` writes down about it. The model here is a small
hand-written one — resolving a real registry is weaver's job and is covered by
each domain's own tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from opentelemetry.conformance._report import Observed, finding_list, read
from opentelemetry.conformance._semconv import _reduce, semconv_coverage

MODEL = {
    "spans": {
        "http.server": {
            "kind": "server",
            "attributes": {
                "http.request.method": "required",
                "http.route": "conditionally_required",
                "url.scheme": "recommended",
                "client.port": "opt_in",
            },
        }
    },
    "metrics": {
        "http.server.request.duration": {
            "attributes": {
                "http.request.method": "required",
                "error.type": "conditionally_required",
            }
        }
    },
    "events": {"some.event": {"attributes": {"a": "recommended"}}},
    "entities": {
        "k8s.pod": {
            "identity": {"k8s.pod.uid": "required"},
            "description": {"k8s.pod.name": "recommended"},
        }
    },
}


def by_kind(_name: str, kind: str, _attributes: object) -> set[str]:
    """Classify every span by its kind, which is all these fixtures need."""
    return {f"http.{kind}"}


def attribute(name: str, value: object = "x", *, advice: str | None = None):
    record: dict[str, object] = {"name": name, "value": value}
    if advice is not None:
        record["live_check_result"] = {"all_advice": [{"id": advice}]}
    return record


def write_report(directory: Path, name: str, **report: object) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(report))


def span_sample(kind: str = "server", *attributes: object) -> dict:
    return {"span": {"name": "GET /", "kind": kind, "attributes": list(attributes)}}


def resource_sample(*attributes: object) -> dict:
    return {"resource": {"attributes": list(attributes)}}


# ── reading reports ────────────────────────────────────────────────


def test_a_span_is_recorded_under_every_type_it_classifies_as(tmp_path) -> None:
    write_report(
        tmp_path, "one", samples=[span_sample("server", attribute("url.scheme"))]
    )

    observed = read(tmp_path, by_kind)

    assert set(observed.spans) == {"http.server"}
    assert observed.spans["http.server"] == {"url.scheme"}


def test_a_span_type_carries_what_any_of_its_samples_had(tmp_path) -> None:
    write_report(
        tmp_path,
        "one",
        samples=[
            span_sample("server", attribute("http.request.method")),
            span_sample(
                "server",
                attribute("http.request.method"),
                attribute("http.route"),
            ),
        ],
    )

    carried = read(tmp_path, by_kind).spans["http.server"]

    assert carried == {"http.request.method", "http.route"}


def test_an_attribute_weaver_rejected_did_not_really_arrive(tmp_path) -> None:
    """A type_mismatch means the name is there holding something disallowed."""
    write_report(
        tmp_path,
        "one",
        samples=[
            span_sample(
                "server",
                attribute("http.route", advice="type_mismatch"),
                attribute("url.scheme", advice="not_stable"),
            )
        ],
    )

    carried = read(tmp_path, by_kind).spans["http.server"]

    assert carried == {"url.scheme"}


def test_a_metric_carries_the_attributes_of_all_its_data_points(
    tmp_path,
) -> None:
    write_report(
        tmp_path,
        "one",
        samples=[
            {
                "metric": {
                    "name": "http.server.request.duration",
                    "data_points": [
                        {"attributes": [attribute("http.request.method")]},
                        {"attributes": [attribute("error.type")]},
                    ],
                }
            }
        ],
    )

    carried = read(tmp_path, by_kind).metrics["http.server.request.duration"]

    assert carried == {"http.request.method", "error.type"}


# ── findings ────────────────────────────────────────────────────────


def advised(*advice: object) -> dict:
    return {"live_check_result": {"all_advice": list(advice)}}


def advice(
    message: str,
    context: object = None,
    advice_id: str = "some_advice",
    level: str = "violation",
    signal_type: str | None = None,
    signal_name: str | None = None,
) -> dict:
    said = {
        "id": advice_id,
        "level": level,
        "message": message,
        "context": context,
    }
    if signal_type is not None:
        said["signal_type"] = signal_type
    if signal_name is not None:
        said["signal_name"] = signal_name
    return said


def test_the_same_finding_seen_twice_is_recorded_once(tmp_path) -> None:
    """One gap reported on every span it touches is still one gap."""
    said = advice("missing server.address", {"attr": "a"})
    write_report(
        tmp_path,
        "one",
        samples=[span_sample("server", advised(said)), advised(said)],
    )
    write_report(tmp_path, "two", samples=[advised(said)])

    assert finding_list(read(tmp_path, by_kind).findings) == [
        {
            "id": "some_advice",
            "message": "missing server.address",
            "context": {"attr": "a"},
        }
    ]


def test_a_finding_records_the_signal_it_was_reported_on(tmp_path) -> None:
    """Weaver stamps the span or metric it was looking at; a reader needs it."""
    write_report(
        tmp_path,
        "one",
        samples=[
            advised(
                advice(
                    "missing server.address",
                    signal_type="span",
                    signal_name="chat gpt-4o-mini",
                )
            )
        ],
    )

    assert finding_list(read(tmp_path, by_kind).findings) == [
        {
            "id": "some_advice",
            "message": "missing server.address",
            "signal_type": "span",
            "signal_name": "chat gpt-4o-mini",
        }
    ]


def test_the_same_gap_on_two_signals_is_two_findings(tmp_path) -> None:
    """One is fixable without the other, so the file has to say both."""
    write_report(
        tmp_path,
        "one",
        samples=[
            advised(
                advice("missing x", signal_type="span", signal_name="chat"),
                advice("missing x", signal_type="span", signal_name="embeddings"),
            )
        ],
    )

    recorded = finding_list(read(tmp_path, by_kind).findings)

    assert [item["signal_name"] for item in recorded] == ["chat", "embeddings"]


def test_a_finding_about_the_resource_names_no_signal(tmp_path) -> None:
    """Weaver reports one with an empty signal name; it is left out."""
    write_report(
        tmp_path,
        "one",
        samples=[advised(advice("wrong", signal_type="resource", signal_name=""))],
    )

    assert finding_list(read(tmp_path, by_kind).findings) == [
        {
            "id": "some_advice",
            "message": "wrong",
            "signal_type": "resource",
        }
    ]


def test_only_violations_are_recorded(tmp_path) -> None:
    """The rest is what could be better, not what an implementation got wrong."""
    write_report(
        tmp_path,
        "one",
        samples=[
            advised(
                advice("fine", level="information"),
                advice("could be better", level="improvement"),
                advice("wrong"),
            )
        ],
    )

    recorded = finding_list(read(tmp_path, by_kind).findings)

    assert [item["message"] for item in recorded] == ["wrong"]


def test_a_finding_weaver_gave_no_context_for_records_none(tmp_path) -> None:
    """A missing context is left out, not committed as a null."""
    write_report(tmp_path, "one", samples=[advised(advice("no context"))])

    assert finding_list(read(tmp_path, by_kind).findings) == [
        {
            "id": "some_advice",
            "message": "no context",
        }
    ]


def test_findings_are_ordered_by_message(tmp_path) -> None:
    write_report(
        tmp_path,
        "one",
        samples=[advised(advice("z"), advice("a"), advice("n"))],
    )

    recorded = finding_list(read(tmp_path, by_kind).findings)

    assert [item["message"] for item in recorded] == ["a", "n", "z"]


def test_one_message_about_two_things_is_two_findings(tmp_path) -> None:
    write_report(
        tmp_path,
        "one",
        samples=[
            advised(
                advice("attribute missing", {"attr": "b"}),
                advice("attribute missing", {"attr": "a"}),
            )
        ],
    )

    recorded = finding_list(read(tmp_path, by_kind).findings)

    assert [item["context"] for item in recorded] == [
        {"attr": "a"},
        {"attr": "b"},
    ]


def test_the_reduction_records_the_findings_a_run_drew(tmp_path) -> None:
    write_report(
        tmp_path,
        "one",
        samples=[advised(advice("no", {"attr": "a"}))],
    )

    build = semconv_coverage(by_kind, lambda: MODEL)
    data = build(tmp_path, None)  # pyright: ignore[reportArgumentType]

    assert data["findings"] == [  # pyright: ignore[reportIndexIssue]
        {
            "id": "some_advice",
            "message": "no",
            "context": {"attr": "a"},
        }
    ]


def test_a_resource_carries_its_valid_attributes(tmp_path) -> None:
    write_report(
        tmp_path,
        "one",
        samples=[
            resource_sample(
                attribute("k8s.pod.uid"),
                attribute("k8s.pod.name"),
                attribute("bad.attr", advice="type_mismatch"),
            )
        ],
    )

    resources = read(tmp_path, by_kind).resources

    assert resources == {"k8s.pod.uid", "k8s.pod.name"}
# ── reducing against the model ─────────────────────────────────────


def signal(*names: str) -> set[str]:
    return set(names)


def test_an_attribute_counts_when_any_sample_had_it() -> None:
    """Including a required one — a sample missing it is a weaver violation."""
    data = _reduce(
        Observed(spans={"http.server": signal("http.request.method")}),
        MODEL,
    )

    assert data["spans"]["http.server"] == ["http.request.method"]


def test_an_attribute_the_registry_does_not_declare_is_not_coverage() -> None:
    data = _reduce(
        Observed(spans={"http.server": signal("something.custom")}), MODEL
    )

    assert data["spans"] == {}


def test_a_signal_the_registry_does_not_declare_is_dropped() -> None:
    data = _reduce(Observed(metrics={"custom.metric": signal("a")}), MODEL)

    assert data["metrics"] == {}


def test_a_metric_the_run_emitted_bare_is_still_recorded() -> None:
    """Emitting it is a fact; a span type recognised by nothing is not."""
    data = _reduce(
        Observed(
            metrics={"http.server.request.duration": set()},
            spans={"http.server": set()},
        ),
        MODEL,
    )

    assert data["metrics"] == {"http.server.request.duration": []}
    assert data["spans"] == {}


def test_an_entity_is_recorded_when_its_identity_attribute_is_present() -> None:
    data = _reduce(
        Observed(resources={"k8s.pod.uid", "k8s.pod.name"}),
        MODEL,
    )

    assert data["entities"]["k8s.pod"] == {
        "identity": ["k8s.pod.uid"],
        "description": ["k8s.pod.name"],
    }


def test_an_entity_with_no_description_attributes_records_empty_description() -> None:
    data = _reduce(
        Observed(resources={"k8s.pod.uid"}),
        MODEL,
    )

    assert data["entities"]["k8s.pod"] == {
        "identity": ["k8s.pod.uid"],
        "description": [],
    }


def test_an_entity_is_not_recorded_if_only_descriptive_attributes_are_present() -> None:
    """An entity is recognised by its identifying attributes; description alone is not presence."""
    data = _reduce(
        Observed(resources={"k8s.pod.name"}),
        MODEL,
    )

    assert data["entities"] == {}


def test_an_entity_with_multiple_identity_attributes_requires_all_of_them() -> None:
    model = {
        "entities": {
            "service.instance": {
                "identity": {
                    "service.name": "required",
                    "service.instance.id": "required",
                },
                "description": {"service.version": "recommended"},
            }
        }
    }

    partial = _reduce(
        Observed(resources={"service.name", "service.version"}),
        model,
    )
    assert partial["entities"] == {}

    complete = _reduce(
        Observed(
            resources={
                "service.name",
                "service.instance.id",
                "service.version",
            }
        ),
        model,
    )
    assert complete["entities"]["service.instance"] == {
        "identity": [
            "service.instance.id",
            "service.name",
        ],
        "description": [
            "service.version",
        ],
    }


def test_an_entity_the_run_did_not_emit_attributes_for_is_dropped() -> None:
    data = _reduce(
        Observed(resources={"unrelated.resource.attr"}),
        MODEL,
    )

    assert data["entities"] == {}


def test_every_section_is_present_even_when_empty() -> None:
    """A reader can tell "emitted none" from a file that says so."""
    assert _reduce(Observed(), MODEL) == {
        "spans": {},
        "events": {},
        "metrics": {},
        "entities": {},
        "findings": [],
    }


def test_the_file_is_written_in_a_stable_order() -> None:
    """These files are committed and diffed byte for byte."""
    data = _reduce(
        Observed(
            spans={
                "http.server": signal(
                    "url.scheme", "http.request.method", "client.port"
                )
            },
            metrics={"http.server.request.duration": signal("error.type")},
            resources={"k8s.pod.name", "k8s.pod.uid"},
        ),
        MODEL,
    )

    assert list(data) == ["spans", "events", "metrics", "entities", "findings"]
    for section in (data["spans"], data["events"], data["metrics"], data["entities"]):
        assert list(section) == sorted(section)
    assert data["spans"]["http.server"] == sorted(
        data["spans"]["http.server"]
    )
    assert data["entities"]["k8s.pod"] == {
        "identity": ["k8s.pod.uid"],
        "description": ["k8s.pod.name"],
    }
    assert list(data["entities"]["k8s.pod"]) == ["identity", "description"]


def test_a_run_that_produced_no_reports_is_an_error(tmp_path) -> None:
    build = semconv_coverage(by_kind, lambda: MODEL)

    with pytest.raises(RuntimeError, match="produced nothing to record"):
        build(tmp_path / "missing", None)  # pyright: ignore[reportArgumentType]


def test_read_uses_declared_match_type(tmp_path) -> None:
    # Set up scenario_spec with a match that declares a type
    match = SimpleNamespace(
        attributes={"gen_ai.operation.name": "run_step"},
        kind="internal",
        type="gen_ai.run_step.internal",
    )
    expectation = SimpleNamespace(match=match)
    scenario_spec = SimpleNamespace(spans=[expectation])
    spec = SimpleNamespace(scenarios={"one": scenario_spec})

    write_report(
        tmp_path,
        "one",
        samples=[
            span_sample(
                "internal",
                attribute("gen_ai.operation.name", "run_step"),
                attribute("gen_ai.step.name", "step1"),
            )
        ],
    )

    # by_kind classifies internal spans as http.internal
    # but the matcher type overrides it.
    observed = read(tmp_path, by_kind, spec)  # pyright: ignore[reportArgumentType]

    assert set(observed.spans) == {"gen_ai.run_step.internal"}
    assert observed.spans["gen_ai.run_step.internal"] == {
        "gen_ai.operation.name",
        "gen_ai.step.name",
    }
