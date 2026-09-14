# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""How to recognise database client span types."""

from __future__ import annotations

from typing import Any, Callable, Mapping

_SUPPORTED_SYSTEM_SPAN_TYPES = {
    "mariadb": "db.mariadb.client",
    "mongodb": "db.mongodb.client",
    "postgresql": "db.postgresql.client",
}


def classify_span(
    span_name: str, span_kind: str, attributes: Mapping[str, object]
) -> set[str]:
    """Return the database span types described by a client span."""
    del span_name
    kind = span_kind.upper().removeprefix("SPAN_KIND_")
    if kind != "CLIENT":
        return set()

    system = attributes.get("db.system.name")
    if not isinstance(system, str):
        return set()

    if specific := _SUPPORTED_SYSTEM_SPAN_TYPES.get(system):
        return {specific}
    return set()


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
