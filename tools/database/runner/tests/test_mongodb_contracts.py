# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""MongoDB packages share driver-specific telemetry contracts."""

from pathlib import Path

import pytest
import yaml

from opentelemetry.conformance import load_spec
from opentelemetry.conformance._checks import ObservedSpan, _check_spans

_DATABASE = Path(__file__).parents[4] / "scenarios" / "database"


@pytest.mark.parametrize("driver", ["sync", "reactive"])
@pytest.mark.parametrize(
    "mode", ["opentelemetry-javaagent", "opentelemetry-library"]
)
def test_packages_use_shared_contracts_without_local_expectations(
    driver: str, mode: str
) -> None:
    directory = _DATABASE / "java" / "mongodb" / driver / mode
    package = yaml.safe_load(
        (directory / "conformance.yaml").read_text(encoding="utf-8")
    )
    assert (directory / package["scenario_contract"]).resolve() == (
        _DATABASE
        / "contracts"
        / ("mongodb-reactive.yaml" if driver == "reactive" else "mongodb.yaml")
    ).resolve()
    assert set(package["scenarios"]) == {
        "find",
        "update",
        "delete",
        "aggregate",
    }
    assert all(
        set(scenario) == {"run"} for scenario in package["scenarios"].values()
    )

    spec = load_spec(directory)
    for scenario in spec.scenarios.values():
        assert scenario.spans is not None
        assert len(scenario.spans) == 2
        assert all(span.count == 1 for span in scenario.spans)
        assert scenario.metrics == ("db.client.operation.duration",)
        assert scenario.events == ()


@pytest.mark.parametrize("driver", ["sync", "reactive"])
@pytest.mark.parametrize(
    "mode", ["opentelemetry-javaagent", "opentelemetry-library"]
)
@pytest.mark.parametrize("include_summary", [False, True])
def test_contracts_accept_spans_with_or_without_query_summaries(
    driver: str, mode: str, include_summary: bool
) -> None:
    spec = load_spec(_DATABASE / "java" / "mongodb" / driver / mode)
    for scenario in spec.scenarios.values():
        assert scenario.spans is not None
        observed = []
        for expectation in scenario.spans:
            assert "db.query.summary" not in expectation.attributes
            attributes = dict(expectation.match.attributes)
            for name, matcher in expectation.attributes.items():
                if matcher.present is False:
                    continue
                attributes[name] = 27017 if matcher.present else matcher.equals
            if include_summary:
                attributes["db.query.summary"] = (
                    f"{attributes['db.operation.name']} items"
                )
            observed.append(
                ObservedSpan(
                    name=str(attributes["db.operation.name"]),
                    kind="CLIENT",
                    attributes=attributes,
                )
            )

        assert _check_spans(scenario, observed) == []


def test_driver_contracts_only_differ_in_aggregate_cursor() -> None:
    synchronous = yaml.safe_load(
        (_DATABASE / "contracts" / "mongodb.yaml").read_text(encoding="utf-8")
    )
    reactive = yaml.safe_load(
        (_DATABASE / "contracts" / "mongodb-reactive.yaml").read_text(
            encoding="utf-8"
        )
    )
    synchronous["scenarios"]["aggregate"]["spans"][0]["expect"]["attributes"][
        "db.query.text"
    ] = (
        '{"aggregate": "items", "pipeline": [{"$match": {"_id": "?"}}], '
        '"cursor": {"batchSize": "?"}, "$db": "?", "lsid": {"id": "?"}}'
    )

    assert reactive == synchronous
