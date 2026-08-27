# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""How to recognise database client span types."""

from __future__ import annotations

from typing import Any, Callable, Mapping

_SQL_SYSTEMS = frozenset(
    {
        "actian.ingres",
        "cockroachdb",
        "derby",
        "firebirdsql",
        "h2database",
        "hsqldb",
        "ibm.db2",
        "mariadb",
        "microsoft.sql_server",
        "mysql",
        "oracle.db",
        "other_sql",
        "postgresql",
        "sap.maxdb",
        "sqlite",
        "trino",
    }
)


def classify_span(
    span_name: str, span_kind: str, attributes: Mapping[str, object]
) -> set[str]:
    """Return the database span types described by a client span."""
    del span_name
    kind = span_kind.upper().removeprefix("SPAN_KIND_")
    if kind not in {"CLIENT", "INTERNAL"}:
        return set()

    system = attributes.get("db.system.name")
    if not isinstance(system, str):
        return set()

    span_types = {"db.client"}
    if kind == "CLIENT" and system in _SQL_SYSTEMS:
        span_types.add("db.sql.client")
    return span_types


def classifier(
    coverage_model: Mapping[str, Any],
) -> Callable[[str, str, Mapping[str, object]], set[str]]:
    """Build a classifier restricted to span types in the resolved registry."""
    declared = frozenset(coverage_model["spans"])

    def classify(
        span_name: str, span_kind: str, attributes: Mapping[str, object]
    ) -> set[str]:
        return classify_span(span_name, span_kind, attributes) & declared

    return classify
