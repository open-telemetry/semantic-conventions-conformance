# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Recognising database client spans."""

from __future__ import annotations

import pytest

from database_conformance import classify_span


@pytest.mark.parametrize("kind", ["client", "CLIENT", "SPAN_KIND_CLIENT"])
def test_postgresql_client_span_uses_the_vendor_refinement(kind: str) -> None:
    assert classify_span("SELECT", kind, {"db.system.name": "postgresql"}) == {
        "db.postgresql.client"
    }


def test_mariadb_client_span_uses_the_vendor_refinement() -> None:
    assert classify_span(
        "SELECT", "CLIENT", {"db.system.name": "mariadb"}
    ) == {"db.mariadb.client"}


@pytest.mark.parametrize("system", ["sqlite", "redis"])
def test_an_unsupported_database_system_is_not_classified(system: str) -> None:
    assert (
        classify_span("SELECT", "CLIENT", {"db.system.name": system}) == set()
    )


def test_a_span_without_a_database_system_is_not_a_database_span() -> None:
    assert (
        classify_span("GET", "CLIENT", {"http.request.method": "GET"}) == set()
    )


def test_a_span_of_an_unrelated_kind_is_not_a_database_client_span() -> None:
    attributes = {"db.system.name": "postgresql"}

    assert classify_span("SELECT", "INTERNAL", attributes) == set()
    assert classify_span("SELECT", "SERVER", attributes) == set()
    assert classify_span("SELECT", "PRODUCER", attributes) == set()
