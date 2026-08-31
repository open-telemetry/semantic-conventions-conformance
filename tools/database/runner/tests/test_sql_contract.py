# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""SQL workload contracts agree with the runner and telemetry contracts."""

import json
from pathlib import Path

import yaml

from database_conformance import _BACKENDS

_REPOSITORY = Path(__file__).parents[4]
_CONTRACTS = Path(__file__).parents[2] / "sql-test-client" / "contracts"
_TELEMETRY_CONTRACTS = _REPOSITORY / "scenarios" / "database" / "contracts"
_SCENARIO_PACKAGES = _REPOSITORY / "scenarios" / "database"


def _contracts() -> list[tuple[Path, dict[str, object]]]:
    paths = sorted(_CONTRACTS.glob("*.json"))
    assert paths
    return [
        (path, json.loads(path.read_text(encoding="utf-8")))
        for path in paths
    ]


def test_runner_supports_every_sql_contract_backend() -> None:
    for path, document in _contracts():
        backend = document["backend"]
        assert backend == path.stem
        assert backend in _BACKENDS


def test_sql_scenarios_match_vendor_telemetry_contracts() -> None:
    for _, document in _contracts():
        backend = document["backend"]
        scenarios = document["scenarios"]
        assert isinstance(backend, str)
        assert isinstance(scenarios, list)
        workload_names = [scenario["name"] for scenario in scenarios]
        assert len(workload_names) == len(set(workload_names))

        telemetry_path = _TELEMETRY_CONTRACTS / f"{backend}.yaml"
        telemetry = yaml.safe_load(telemetry_path.read_text(encoding="utf-8"))
        assert set(workload_names) == set(telemetry["scenarios"])


def test_sql_scenarios_are_wired_by_every_matching_package() -> None:
    for _, document in _contracts():
        backend = document["backend"]
        scenarios = document["scenarios"]
        assert isinstance(backend, str)
        assert isinstance(scenarios, list)
        workload_names = {scenario["name"] for scenario in scenarios}

        packages: list[tuple[Path, dict[str, object]]] = []
        for path in _SCENARIO_PACKAGES.rglob("conformance.yaml"):
            package = yaml.safe_load(path.read_text(encoding="utf-8"))
            runner_config = package.get("runner_config", {})
            if runner_config.get("backend") == backend:
                packages.append((path, package))

        assert packages
        for path, package in packages:
            package_scenarios = package["scenarios"]
            assert set(package_scenarios) == workload_names, path
            for name, scenario in package_scenarios.items():
                assert scenario["run"].split()[-1] == name, path
