# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Known database gaps are findings, including incorrect values."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from opentelemetry.conformance import load_spec
from opentelemetry.conformance._checks import check
from opentelemetry.test.weaver_live_check import LiveCheckReport

ROOT = Path(__file__).resolve().parents[4] / "scenarios/database/java"
CASES = [
    *[
        (
            f"redis/{client}/{mode}",
            "error",
            -1,
            {"db.operation.name": "LPUSH"},
            {"db.response.status_code": "WRONGTYPE"},
        )
        for client, mode in [
            ("jedis", "opentelemetry-javaagent"),
            ("lettuce", "opentelemetry-javaagent"),
            ("lettuce", "opentelemetry-library"),
            ("rediscala", "opentelemetry-javaagent"),
            ("redisson", "opentelemetry-javaagent"),
        ]
    ],
    *[
        (
            f"cassandra/java-driver/{mode}",
            "error",
            0,
            {"db.system.name": "cassandra"},
            {"db.response.status_code": "8704"},
        )
        for mode in ["opentelemetry-javaagent", "opentelemetry-library"]
    ],
    *[
        (
            f"postgresql/r2dbc/{mode}",
            "error",
            0,
            {"db.system.name": "postgresql", "db.namespace": "conformance"},
            {"db.response.status_code": "42P01"},
        )
        for mode in ["opentelemetry-javaagent", "opentelemetry-library"]
    ],
    *[
        (
            f"mongodb/{client}/{mode}",
            "error",
            0,
            {
                "db.system.name": "mongodb",
                "db.operation.name": "find",
                "error.type": "2",
            },
            {"db.response.status_code": "2"},
        )
        for client in ["sync", "reactive"]
        for mode in ["opentelemetry-javaagent", "opentelemetry-library"]
    ],
    *[
        (
            f"oracle/jdbc/{mode}",
            scenario,
            0,
            {"db.system.name": "oracle.db", "db.namespace": "freepdb1"},
            {"db.namespace": "FREE"},
        )
        for mode in ["opentelemetry-javaagent", "opentelemetry-library"]
        for scenario in ["0000", "0001", "0002", "0003"]
    ],
    (
        "hbase/hbase-client/native",
        "batch",
        0,
        {
            "db.system": "hbase",
            "db.operation": "BATCH",
            "db.hbase.table": "conformance:items",
            "db.hbase.container_operations": ["PUT"],
        },
        {"db.operation.name": "BATCH PUT", "db.operation.batch.size": 2},
    ),
]


@pytest.mark.parametrize(
    ("path", "name", "index", "native", "required"), CASES
)
@pytest.mark.parametrize("state", ["missing", "incorrect", "conformant"])
def test_database_semantics(
    path: str,
    name: str,
    index: int,
    native: dict[str, object],
    required: dict[str, object],
    state: str,
) -> None:
    scenario = load_spec(ROOT / path).scenarios[name]
    assert scenario.spans is not None
    # Existing tests cover workload attributes. Isolate the semantic assertion
    # while retaining its real selector and span count.
    scenario = replace(
        scenario,
        spans=(replace(scenario.spans[index], attributes={}),),
        metrics=None,
        events=None,
    )
    attributes = dict(native)
    if state == "missing":
        for key in required:
            attributes.pop(key, None)
    else:
        attributes.update(
            required
            if state == "conformant"
            else {key: "incorrect" for key in required}
        )
    observed = LiveCheckReport(
        {
            "samples": [
                {
                    "span": {
                        "name": "database operation",
                        "kind": "CLIENT",
                        "attributes": [
                            {"name": key, "value": value}
                            for key, value in attributes.items()
                        ],
                    }
                }
            ],
            "statistics": {},
        }
    )
    findings = check(scenario, observed)
    assert not findings.failures
    expect_findings = state != "conformant" and not (
        path.startswith("oracle/") and state == "missing"
    )
    assert {
        entry["context"]["attribute_key"] for entry in findings.contract_checks
    } == (set(required) if expect_findings else set())
    assert bool(findings.violations) is expect_findings
