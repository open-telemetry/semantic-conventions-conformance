# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The committed Rust client config must select a request at startup."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

from opentelemetry.conformance import WeaverSpec, _session, load_spec
from opentelemetry.conformance._session import ConformanceSession


def test_awc_client_runs_each_contract_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = (
        Path(__file__).resolve().parents[3]
        / "scenarios"
        / "http"
        / "rust"
        / "awc"
        / "opentelemetry-actix-web"
        / "client"
    )
    spec = load_spec(directory)
    captured: list[tuple[tuple[str, ...], Path, Mapping[str, str]]] = []

    def run(
        command: tuple[str, ...], *, cwd: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        captured.append((command, cwd, env))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_session, "_run_command", run)
    monkeypatch.delenv("OTEL_CONFORMANCE_SCENARIO_INDEX", raising=False)
    opened = ConformanceSession(
        spec,
        tmp_path / "reports",
        variables={"MOCK_SERVER_URL": "http://mock-server"},
        weaver=WeaverSpec(registry="model"),
        env={},
        data_file=tmp_path / "data.json",
        build_data=lambda reports, package: {},
    )

    assert list(spec.scenarios) == ["0000", "0001", "0002", "0003", "0004"]
    assert spec.setup == ("otel-conformance-rust", "build")
    assert spec.server.run == ("http-mock-server", "--port", "${PORT}")
    for index, scenario in enumerate(spec.scenarios.values()):
        assert scenario.index == index
        assert scenario.spans is not None
        assert len(scenario.spans) == 1
        assert scenario.spans[0].count == 1
        assert scenario.spans[0].match.kind == "CLIENT"
        assert scenario.events == ()
        opened._execute(scenario, "http://collector")

    assert len(captured) == 5
    for index, (command, cwd, env) in enumerate(captured):
        assert command == ("otel-conformance-rust", "run")
        assert cwd == directory
        assert env["OTEL_CONFORMANCE_SCENARIO_INDEX"] == str(index)
        assert env["MOCK_SERVER_URL"] == "http://mock-server"
        assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://collector"
