# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Stable database expectations for native HBase telemetry."""

from __future__ import annotations

from pathlib import Path

import pytest

from opentelemetry.conformance import load_spec
from opentelemetry.conformance._checks import ObservedSpan, _check_spans


@pytest.mark.parametrize(
    ("scenario", "operation"),
    [
        ("get", "GET"),
        ("put", "PUT"),
        ("scan", "SCAN"),
        ("batch", "BATCH"),
    ],
)
@pytest.mark.parametrize(
    ("server_attributes", "valid"),
    [
        ({"server.address": "127.0.0.1", "server.port": 16000}, True),
        ({"server.address": "localhost"}, False),
        (
            {"server.address": "127.0.0.1", "server.port": 2181},
            False,
        ),
    ],
)
def test_hbase_contract_requires_the_bootstrap_address(
    scenario: str,
    operation: str,
    server_attributes: dict[str, object],
    valid: bool,
) -> None:
    root = Path(__file__).resolve().parents[4]
    spec = load_spec(
        root
        / "scenarios/database/java/hbase"
        / "native"
    ).scenarios[scenario]
    attributes: dict[str, object] = {
        "db.system.name": "hbase",
        "db.operation.name": operation,
        "db.collection.name": "items",
        "db.namespace": "conformance",
        **server_attributes,
    }
    if scenario == "batch":
        attributes["db.operation.batch.size"] = 2
    spans = [
        ObservedSpan(f"{operation} items", "CLIENT", attributes),
        ObservedSpan(
            "SCAN meta",
            "CLIENT",
            {
                "db.system.name": "hbase",
                "db.operation.name": "SCAN",
                "db.collection.name": "meta",
                "db.namespace": "hbase",
                **server_attributes,
            },
        ),
    ]

    assert (not _check_spans(spec, spans)) is valid


def test_hbase_native_package_keeps_strict_expectations_without_an_agent() -> None:
    root = Path(__file__).resolve().parents[4]
    spec = load_spec(root / "scenarios/database/java/hbase/native")
    assert spec.runner_config == {"backend": "hbase"}
    assert spec.instrumentation_library == "org.apache.hbase:hbase-client"
    assert spec.setup == ("otel-conformance-java", "prepare", "hbase:native")
    assert set(spec.scenarios) == {"get", "put", "scan", "batch"}
    for name, scenario in spec.scenarios.items():
        assert scenario.run == (
            "otel-conformance-java",
            "run",
            "hbase:native",
            "HbaseNativeScenario",
            name,
        )
        assert not scenario.expected_violations
        assert scenario.metrics is not None
        assert "db.client.operation.duration" in scenario.metrics
        assert _check_spans(
            scenario,
            [ObservedSpan("GET conformance:items", "CLIENT", {"db.system": "hbase"})],
        )
