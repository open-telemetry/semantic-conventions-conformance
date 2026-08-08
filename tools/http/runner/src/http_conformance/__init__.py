# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance runs against the HTTP semantic conventions.

The whole domain: the upstream registry at a pinned tag, how to recognise an
HTTP span, and one advice policy. Everything a directory declaring
``runner: http-conformance`` then gets is the runner's :class:`~.Domain`.
"""

from pathlib import Path

from opentelemetry.conformance import Domain, require_pin

from ._coverage import classifier, classify_span

_HERE = Path(__file__).parent

DOMAIN = Domain(
    name="http-conformance",
    repo="open-telemetry/semantic-conventions",
    ref=require_pin(_HERE / "versions.env", "SEMCONV_REF"),
    classifier=classifier,
    policies=_HERE / "policies",
)

# Named in pyproject.toml: the runner entry point and the console script.
http_session = DOMAIN.session
cli = DOMAIN.cli

__all__ = ["DOMAIN", "classify_span", "cli", "http_session"]
