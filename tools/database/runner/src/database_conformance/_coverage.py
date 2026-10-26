# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""How to recognise database client span types."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from ._registry import BACKENDS

_SYSTEM_SPAN_TYPES: dict[str, set[str]] = {}
for registration in BACKENDS.values():
    _SYSTEM_SPAN_TYPES.setdefault(registration.system, set()).add(
        registration.client_span_type
    )


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

    return _SYSTEM_SPAN_TYPES.get(system, set()).copy()


def classifier(
    coverage_model: Mapping[str, Any],
) -> Callable[[str, str, Mapping[str, object]], set[str]]:
    """Build a classifier restricted to span types in the resolved registry."""
    spans = coverage_model["spans"]
    client_span_types = {
        registration.client_span_type
        for registration in BACKENDS.values()
        if isinstance(spans.get(registration.client_span_type), Mapping)
        and spans[registration.client_span_type].get("kind") == "client"
    }

    def classify(
        span_name: str, span_kind: str, attributes: Mapping[str, object]
    ) -> set[str]:
        return classify_span(span_name, span_kind, attributes) & client_span_types

    return classify
