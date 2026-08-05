# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""HTTP-specific span classification heuristics."""

from __future__ import annotations


def _has_any_attr(attrs: dict[str, object], *names: str) -> bool:
    return any(attrs.get(name) is not None for name in names)


def _is_http_span(attrs: dict[str, object]) -> bool:
    return any(
        name.startswith("http.") or name in ("url.full", "url.path", "url.scheme", "url.query") for name in attrs
    )


def classify_span(span_name: str, span_kind: str, span_attrs: dict[str, object]) -> set[str]:
    """Classify an HTTP span based on span kind and attributes."""
    if not _is_http_span(span_attrs):
        return set()

    name = span_name.strip()
    kind = span_kind.upper() if span_kind else ""
    classified: set[str] = set()

    if kind in {"SPAN_KIND_CLIENT", "CLIENT"}:
        classified.add("client")
    elif kind in {"SPAN_KIND_SERVER", "SERVER"}:
        classified.add("server")
    elif _has_any_attr(span_attrs, "url.full", "http.request.resend_count"):
        classified.add("client")
    elif _has_any_attr(span_attrs, "url.path", "http.route", "client.address"):
        classified.add("server")
    elif name in {"documentFetch", "resourceFetch"}:
        classified.add("client")

    return classified
