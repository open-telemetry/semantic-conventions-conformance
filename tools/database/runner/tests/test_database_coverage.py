# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Recognising database client spans."""

from __future__ import annotations

import pytest

from database_conformance import classify_span
from database_conformance._coverage import classifier


@pytest.mark.parametrize("kind", ["client", "CLIENT", "SPAN_KIND_CLIENT"])
def test_postgresql_client_span_uses_the_vendor_refinement(kind: str) -> None:
    assert classify_span("SELECT", kind, {"db.system.name": "postgresql"}) == {
        "db.postgresql.client"
    }


def test_mariadb_client_span_uses_the_vendor_refinement() -> None:
    assert classify_span(
        "SELECT", "CLIENT", {"db.system.name": "mariadb"}
    ) == {"db.mariadb.client"}


def test_redis_client_span_uses_the_vendor_refinement() -> None:
    assert classify_span("GET", "CLIENT", {"db.system.name": "redis"}) == {
        "db.redis.client"
    }


def test_hbase_client_span_uses_the_vendor_refinement() -> None:
    assert classify_span(
        "Get items", "CLIENT", {"db.system.name": "hbase"}
    ) == {"db.hbase.client"}


def test_an_unsupported_database_system_is_not_classified() -> None:
    assert (
        classify_span("SELECT", "CLIENT", {"db.system.name": "sqlite"}) == set()
    )


def test_sql_server_client_span_uses_the_vendor_refinement() -> None:
    assert classify_span(
        "SELECT", "CLIENT", {"db.system.name": "microsoft.sql_server"}
    ) == {"db.sql_server.client"}


def test_a_span_without_a_database_system_is_not_a_database_span() -> None:
    assert (
        classify_span("GET", "CLIENT", {"http.request.method": "GET"}) == set()
    )


def test_classification_results_do_not_share_mutable_state() -> None:
    classify_span("SELECT", "CLIENT", {"db.system.name": "postgresql"}).clear()

    assert classify_span("SELECT", "CLIENT", {"db.system.name": "postgresql"}) == {
        "db.postgresql.client"
    }


def test_a_span_of_an_unrelated_kind_is_not_a_database_client_span() -> None:
    attributes = {"db.system.name": "postgresql"}

    assert classify_span("SELECT", "INTERNAL", attributes) == set()
    assert classify_span("SELECT", "SERVER", attributes) == set()
    assert classify_span("SELECT", "PRODUCER", attributes) == set()


def test_classifier_only_returns_registered_client_types_in_the_registry() -> None:
    classify = classifier(
        {
            "spans": {
                "db.postgresql.client": {"kind": "server"},
                "db.redis.client": {"kind": "client"},
            }
        }
    )

    assert classify("SELECT", "CLIENT", {"db.system.name": "postgresql"}) == set()
    assert classify("SELECT", "CLIENT", {"db.system.name": "mariadb"}) == set()
    assert classify("GET", "CLIENT", {"db.system.name": "redis"}) == {
        "db.redis.client"
    }
