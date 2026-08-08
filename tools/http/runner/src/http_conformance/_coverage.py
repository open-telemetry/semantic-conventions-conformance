# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""How to recognise an HTTP span type."""

from __future__ import annotations

from typing import Any, Callable, Mapping

# Required on both HTTP span types, and on nothing else. A database or RPC
# span may well carry http.response.status_code or url.full; it is not an HTTP
# span, and must not be recorded as coverage of one.
_IDENTIFYING_ATTRIBUTE = "http.request.method"

# The conventions pin the kind — CLIENT for one type, SERVER for the other —
# so a span of any other kind isn't a conforming HTTP span. Weaver reports the
# kind itself; recording coverage for it would credit conformance the run
# didn't have.
_KINDS = ("CLIENT", "SERVER")


def classify_span(
    span_name: str, span_kind: str, attributes: Mapping[str, object]
) -> set[str]:
    """The HTTP span types a span belongs to.

    ``span_name`` is unused; it is accepted to match the runner's signature.
    """
    del span_name
    if attributes.get(_IDENTIFYING_ATTRIBUTE) is None:
        return set()
    kind = span_kind.upper().removeprefix("SPAN_KIND_")
    return {f"http.{kind.lower()}"} if kind in _KINDS else set()


def classifier(
    coverage_model: Mapping[str, Any],
) -> Callable[[str, str, Mapping[str, object]], set[str]]:
    """The runner asks for a classifier per run; HTTP's needs no registry."""
    del coverage_model
    return classify_span
