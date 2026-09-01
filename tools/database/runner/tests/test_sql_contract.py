# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Combined SQL contracts agree with the runner and scenario packages."""

from pathlib import Path

import yaml

from database_conformance import _BACKENDS
from opentelemetry.conformance import load_spec

_REPOSITORY = Path(__file__).parents[4]
_CONTRACTS = Path(__file__).parents[2] / "sql-test-client" / "contracts"
_SCENARIO_PACKAGES = _REPOSITORY / "scenarios" / "database"


def _contracts() -> list[tuple[Path, dict[str, object]]]:
    paths = sorted(_CONTRACTS.glob("*.yaml"))
    assert paths
    return [
        (path, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in paths
    ]


def test_sql_contract_metadata_matches_its_resource_and_runner() -> None:
    for path, document in _contracts():
        assert set(document) == {"backend", "description", "scenarios"}
        backend = document["backend"]
        assert backend == path.stem
        assert backend in _BACKENDS
        assert isinstance(document["description"], str)
        assert document["description"]


def test_sql_scenarios_combine_actions_and_expectations() -> None:
    for _, document in _contracts():
        scenarios = document["scenarios"]
        assert isinstance(scenarios, list)
        assert scenarios
        for scenario in scenarios:
            assert isinstance(scenario, dict)
            assert set(scenario) == {"description", "action", "expect"}
            assert isinstance(scenario["description"], str)
            assert scenario["description"]
            assert isinstance(scenario["action"], dict)
            assert isinstance(scenario["expect"], dict)


def test_sql_scenarios_are_wired_by_every_matching_package() -> None:
    for contract_path, document in _contracts():
        backend = document["backend"]
        scenarios = document["scenarios"]
        assert isinstance(backend, str)
        assert isinstance(scenarios, list)

        packages: list[tuple[Path, dict[str, object]]] = []
        for path in _SCENARIO_PACKAGES.rglob("conformance.yaml"):
            package = yaml.safe_load(path.read_text(encoding="utf-8"))
            runner_config = package.get("runner_config", {})
            if runner_config.get("backend") == backend:
                packages.append((path, package))

        assert packages
        for path, package in packages:
            scenario_contract = path.parent / package["scenario_contract"]
            assert scenario_contract.resolve() == contract_path.resolve(), path
            assert "scenarios" not in package, path
            assert isinstance(package["scenario_run"], str), path

            spec = load_spec(path.parent)
            assert [
                scenario.index for scenario in spec.scenarios.values()
            ] == list(range(len(scenarios))), path
            assert [
                scenario.description for scenario in spec.scenarios.values()
            ] == [scenario["description"] for scenario in scenarios], path
