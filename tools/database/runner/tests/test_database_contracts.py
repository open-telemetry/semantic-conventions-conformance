# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Native workload expectations stay separate from semantic conformance."""

from __future__ import annotations

from pathlib import Path

import pytest

from database_conformance import classify_span
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
    ("overrides", "kind", "count", "valid"),
    [
        ({}, "CLIENT", 1, True),
        ({}, "CLIENT", 0, False),
        ({}, "CLIENT", 2, False),
        ({}, "INTERNAL", 1, False),
        ({"db.system": "other"}, "CLIENT", 1, False),
        ({"db.operation": "OTHER"}, "CLIENT", 1, False),
        ({"db.hbase.table": "hbase:meta"}, "CLIENT", 1, False),
        ({"db.name": "other"}, "CLIENT", 1, False),
        ({"db.connection_string": "127.0.0.1:2181"}, "CLIENT", 1, False),
    ],
)
def test_hbase_contract_requires_the_native_workload_span(
    scenario: str,
    operation: str,
    overrides: dict[str, object],
    kind: str,
    count: int,
    valid: bool,
) -> None:
    root = Path(__file__).resolve().parents[4]
    spec = load_spec(root / "scenarios/database/java/hbase/native").scenarios[
        scenario
    ]
    attributes: dict[str, object] = {
        "db.system": "hbase",
        "db.operation": operation,
        "db.hbase.table": "conformance:items",
        "db.name": "conformance",
        "db.connection_string": "127.0.0.1:16000",
        **overrides,
    }
    if scenario == "batch":
        attributes["db.hbase.container_operations"] = ["PUT"]
    spans = [
        *[
            ObservedSpan(f"{operation} conformance:items", kind, attributes)
            for _ in range(count)
        ],
        ObservedSpan(
            "SCAN hbase:meta",
            "CLIENT",
            {
                "db.system": "hbase",
                "db.operation": "SCAN",
                "db.hbase.table": "hbase:meta",
            },
        ),
        ObservedSpan(
            "hbase.pb.ClientService/Scan",
            "CLIENT",
            {"rpc.system": "HBASE_RPC", "rpc.method": "Scan"},
        ),
        ObservedSpan("AsyncConnection.close", "INTERNAL", {}),
    ]

    assert (not _check_spans(spec, spans)) is valid
    assert classify_span(f"{operation} conformance:items", kind, attributes) == set()


@pytest.mark.parametrize("operations", [[], ["GET"], ["PUT", "GET"]])
def test_hbase_batch_requires_native_put_operations(operations: list[str]) -> None:
    root = Path(__file__).resolve().parents[4]
    spec = load_spec(root / "scenarios/database/java/hbase/native").scenarios[
        "batch"
    ]
    assert _check_spans(
        spec,
        [
            ObservedSpan(
                "BATCH conformance:items",
                "CLIENT",
                {
                    "db.system": "hbase",
                    "db.operation": "BATCH",
                    "db.hbase.table": "conformance:items",
                    "db.name": "conformance",
                    "db.connection_string": "127.0.0.1:16000",
                    "db.hbase.container_operations": operations,
                },
            )
        ],
    )


def test_hbase_contract_rejects_unrelated_client_spans() -> None:
    root = Path(__file__).resolve().parents[4]
    spec = load_spec(root / "scenarios/database/java/hbase/native").scenarios[
        "get"
    ]
    failures = _check_spans(
        spec,
        [
            ObservedSpan(
                "GET conformance:items",
                "CLIENT",
                {
                    "db.system": "hbase",
                    "db.operation": "GET",
                    "db.hbase.table": "conformance:items",
                    "db.name": "conformance",
                    "db.connection_string": "127.0.0.1:16000",
                },
            ),
            ObservedSpan("unrelated", "CLIENT", {}),
        ],
    )
    assert len(failures) == 1
    assert "1 undeclared span(s): ['unrelated']" in failures[0]


def test_hbase_native_package_keeps_emission_checks_without_waivers_or_agent() -> None:
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
        assert scenario.metrics == ("queueSize",)
        assert scenario.events == ()
        assert scenario.spans is not None
        assert all(expectation.match.type is None for expectation in scenario.spans)
        assert scenario.spans[0].count == 1
        scope = scenario.spans[0].instrumentation_scope
        assert scope is not None
        assert scope.name is not None
        assert scope.name.equals == "org.apache.hbase"
        assert scope.version is not None
        assert scope.version.present is True
        assert scope.schema_url is None
        assert _check_spans(scenario, [])
