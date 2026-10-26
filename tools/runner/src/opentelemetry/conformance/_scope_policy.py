# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Render scenario instrumentation-scope expectations as a Rego policy."""

from __future__ import annotations

import json
from pathlib import Path

from ._spans import span_kind
from ._spec import (
    AttributeMatcher,
    InstrumentationScopeExpectation,
    SpanExpectation,
)

_TEMPLATE = (
    Path(__file__).parent
    / "policies"
    / "instrumentation_scope_validation.rego.template"
)
_MARKER = "__INSTRUMENTATION_SCOPE_EXPECTATION__"


def render(spans: tuple[SpanExpectation, ...] | None) -> str:
    """Return the default and signal-specific scope checks."""
    rendered = {
        "global": {
            "name": {"present": True},
            "schema_url": {"present": True},
        },
        "spans": [
            {
                "match": {
                    "attributes": dict(expectation.match.attributes),
                    **(
                        {"kind": span_kind(expectation.match.kind).lower()}
                        if expectation.match.kind is not None
                        else {}
                    ),
                },
                "scope": _fields(expectation.instrumentation_scope),
            }
            for expectation in spans or ()
            if expectation.instrumentation_scope is not None
        ],
    }

    return _TEMPLATE.read_text(encoding="utf-8").replace(
        _MARKER, json.dumps(rendered, sort_keys=True)
    )


def _fields(
    expectation: InstrumentationScopeExpectation | None,
) -> dict[str, dict[str, object]]:
    fields: dict[str, dict[str, object]] = {}
    if expectation is None:
        return fields
    for name, matcher in (
        ("name", expectation.name),
        ("version", expectation.version),
        ("schema_url", expectation.schema_url),
    ):
        if matcher is not None:
            fields[name] = _matcher(matcher)

    return fields


def _matcher(matcher: AttributeMatcher) -> dict[str, object]:
    if matcher.present is not None:
        return {"present": matcher.present}
    return {"equals": matcher.equals}
