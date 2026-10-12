# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""HBase expectations against the Java agent's observed cluster address."""

from __future__ import annotations

from pathlib import Path

import pytest

from opentelemetry.conformance import load_spec
from opentelemetry.conformance._checks import ObservedSpan, _check_spans


@pytest.mark.parametrize("backend", ["hbase-1", "hbase-2"])
@pytest.mark.parametrize(
    ("scenario", "operation"),
    [
        ("get", "Get"),
        ("put", "Mutate"),
        ("scan", "Scan"),
        ("batch", "BATCH Mutate"),
    ],
)
@pytest.mark.parametrize(
    ("server_attributes", "valid"),
    [
        ({"server.address": "127.0.0.1:2181:/hbase"}, True),
        ({"server.address": "localhost"}, False),
        (
            {"server.address": "127.0.0.1:2181:/hbase", "server.port": 16020},
            False,
        ),
    ],
)
def test_hbase_contract_matches_the_cluster_not_the_region_server(
    backend: str,
    scenario: str,
    operation: str,
    server_attributes: dict[str, object],
    valid: bool,
) -> None:
    root = Path(__file__).resolve().parents[4]
    spec = load_spec(
        root
        / "scenarios/database/java/hbase"
        / backend
        / "opentelemetry-javaagent"
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
            "Scan meta",
            "CLIENT",
            {
                "db.system.name": "hbase",
                "db.operation.name": "Scan",
                "db.collection.name": "meta",
                "db.namespace": "hbase",
                **server_attributes,
            },
        ),
    ]

    assert (not _check_spans(spec, spans)) is valid
