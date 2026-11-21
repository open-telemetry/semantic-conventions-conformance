# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance runs against browser event semantic conventions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from opentelemetry.conformance import ClassifySpan, Domain, require_pin

_HERE = Path(__file__).parent


def classifier(_coverage_model: Mapping[str, Any]) -> ClassifySpan:
    """Browser scenarios currently measure events, with no span types."""
    return lambda _name, _kind, _attributes: set()


DOMAIN = Domain(
    name="browser-conformance",
    repo="open-telemetry/semantic-conventions",
    ref=require_pin(_HERE / "versions.env", "SEMCONV_REF"),
    classifier=classifier,
)

browser_session = DOMAIN.session
cli = DOMAIN.cli

__all__ = ["DOMAIN", "browser_session", "cli"]
