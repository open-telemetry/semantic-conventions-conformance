# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""MongoDB packages share one telemetry contract."""

from pathlib import Path

import pytest
import yaml

from opentelemetry.conformance import load_spec

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
        _DATABASE / "contracts" / "mongodb.yaml"
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
        assert all(
            "db.query.text" not in span.attributes for span in scenario.spans
        )
        assert scenario.metrics == ("db.client.operation.duration",)
        assert scenario.events == ()
