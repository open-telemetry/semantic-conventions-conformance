# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Recognising database client spans."""

from __future__ import annotations

import pytest

from database_conformance import classify_span


@pytest.mark.parametrize("kind", ["client", "CLIENT", "SPAN_KIND_CLIENT"])
def test_a_sql_client_span_has_general_and_sql_types(kind: str) -> None:
    assert classify_span(
        "SELECT", kind, {"db.system.name": "postgresql"}
    ) == {"db.client", "db.sql.client"}


def test_a_non_sql_database_span_has_the_general_type() -> None:
    assert classify_span(
        "find", "CLIENT", {"db.system.name": "mongodb"}
    ) == {"db.client"}


def test_an_in_memory_database_call_may_be_internal() -> None:
    assert classify_span(
        "SELECT", "INTERNAL", {"db.system.name": "h2database"}
    ) == {"db.client"}


def test_a_span_without_a_database_system_is_not_a_database_span() -> None:
    assert (
        classify_span(
            "GET", "CLIENT", {"http.request.method": "GET"}
        )
        == set()
    )


def test_a_span_of_an_unrelated_kind_is_not_a_database_client_span() -> None:
    attributes = {"db.system.name": "postgresql"}

    assert classify_span("SELECT", "SERVER", attributes) == set()
    assert classify_span("SELECT", "PRODUCER", attributes) == set()
