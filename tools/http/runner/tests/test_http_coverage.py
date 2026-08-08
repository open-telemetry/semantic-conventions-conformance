# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Recognising an HTTP span."""

from __future__ import annotations

import pytest

from http_conformance import classify_span

GET = {"http.request.method": "GET"}


@pytest.mark.parametrize("kind", ["client", "CLIENT", "SPAN_KIND_CLIENT"])
def test_the_span_kind_names_the_type(kind: str) -> None:
    """Weaver reports a kind in either spelling, depending on the exporter."""
    assert classify_span("GET", kind, GET) == {"http.client"}


def test_a_server_span_is_the_server_type() -> None:
    assert classify_span("GET /users/{id}", "SERVER", GET) == {"http.server"}


def test_a_span_without_the_method_is_not_an_http_span() -> None:
    """A database or RPC span carrying HTTP attributes is not HTTP coverage."""
    assert (
        classify_span(
            "SELECT",
            "CLIENT",
            {"db.system.name": "postgresql", "url.full": "http://db/"},
        )
        == set()
    )


def test_a_span_of_neither_kind_is_not_a_conforming_http_span() -> None:
    """The conventions require CLIENT or SERVER; weaver reports the kind.

    Recording it as coverage would credit conformance the run didn't have.
    """
    assert classify_span("GET", "INTERNAL", GET) == set()
    assert classify_span("GET", "", GET) == set()
