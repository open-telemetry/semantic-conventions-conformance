# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared operations on span data."""


def span_kind(kind: str) -> str:
    """Normalize the API, protocol, and Weaver spellings of a span kind."""
    return kind.upper().removeprefix("SPAN_KIND_")
