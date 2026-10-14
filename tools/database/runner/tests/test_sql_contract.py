# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Combined SQL contracts agree with the runner and JDBC packages."""

from pathlib import Path

import pytest
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


def _jdbc_packages() -> list[tuple[Path, dict[str, object]]]:
    return [
        (path, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(
            _SCENARIO_PACKAGES.glob("java/*/jdbc/*/conformance.yaml")
        )
    ]


def test_sql_contract_metadata_matches_its_resource_and_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(_BACKENDS, "non_sql", _BACKENDS["postgresql"])
    contracts = _contracts()
    assert {path.stem for path, _ in contracts} == {
        package["runner_config"]["backend"] for _, package in _jdbc_packages()
    }

    for path, document in contracts:
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


def test_sql_scenarios_are_wired_by_every_matching_jdbc_package() -> None:
    for contract_path, document in _contracts():
        backend = document["backend"]
        scenarios = document["scenarios"]
        assert isinstance(backend, str)
        assert isinstance(scenarios, list)

        packages: list[tuple[Path, dict[str, object]]] = []
        for path, package in _jdbc_packages():
            runner_config = package.get("runner_config", {})
            if runner_config.get("backend") == backend:
                packages.append((path, package))

        assert packages
        for path, package in packages:
            scenario_contract = path.parent / package["scenario_contract"]
            assert scenario_contract.resolve() == contract_path.resolve(), path
            assert "scenarios" not in package, path

            spec = load_spec(path.parent)
            loaded_scenarios = sorted(
                spec.scenarios.values(), key=lambda scenario: scenario.index
            )
            assert [
                scenario.index for scenario in loaded_scenarios
            ] == list(range(len(scenarios))), path
            assert [
                scenario.description for scenario in loaded_scenarios
            ] == [scenario["description"] for scenario in scenarios], path
            assert [
                scenario.action for scenario in loaded_scenarios
            ] == [scenario["action"] for scenario in scenarios], path


def test_package_discovery_only_includes_jdbc(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for backend, client, instrumentation in (
        ("postgresql", "jdbc", "opentelemetry-library"),
        ("postgresql", "r2dbc", "opentelemetry-library"),
        ("redis", "jedis", "opentelemetry-javaagent"),
    ):
        package = tmp_path / "java" / backend / client / instrumentation
        package.mkdir(parents=True)
        (package / "conformance.yaml").write_text(
            f"runner_config:\n  backend: {backend}\n", encoding="utf-8"
        )
    monkeypatch.setitem(globals(), "_SCENARIO_PACKAGES", tmp_path)

    assert _jdbc_packages() == [
        (
            (
                tmp_path / "java" / "postgresql" / "jdbc"
                / "opentelemetry-library" / "conformance.yaml"
            ),
            {"runner_config": {"backend": "postgresql"}},
        ),
    ]
