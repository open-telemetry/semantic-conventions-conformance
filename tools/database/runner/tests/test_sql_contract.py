# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Combined SQL contracts agree with the runner and scenario packages."""

from pathlib import Path

import yaml

from database_conformance import _BACKENDS

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


def test_runner_supports_every_sql_contract_backend() -> None:
    for path, document in _contracts():
        backend = document["backend"]
        assert backend == path.stem
        assert backend in _BACKENDS


def test_sql_scenarios_combine_actions_and_expectations() -> None:
    for _, document in _contracts():
        scenarios = document["scenarios"]
        assert isinstance(scenarios, dict)
        assert scenarios
        for name, scenario in scenarios.items():
            assert isinstance(name, str)
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
        assert isinstance(scenarios, dict)
        workload_names = set(scenarios)

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
            package_scenarios = package["scenarios"]
            assert set(package_scenarios) == workload_names, path
            for name, scenario in package_scenarios.items():
                assert scenario["run"].split()[-1] == name, path
