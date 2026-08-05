# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""HTTP conformance domain entry point."""

from __future__ import annotations

from pathlib import Path

from semconv_conformance.domain import Domain
from semconv_conformance.http.classify import classify_span
from semconv_conformance.http.semconv_model import METRIC_SPECS, SPAN_SPECS, SPAN_TYPE_ORDER
from semconv_conformance.languages import language_display_names

DOMAIN_DIR = Path(__file__).resolve().parent.parent.parent.parent / "http"

_LANGUAGE_DISPLAY_NAMES = language_display_names(DOMAIN_DIR)


DOMAIN = Domain(
    name="http",
    domain_dir=DOMAIN_DIR,
    language_display_names=_LANGUAGE_DISPLAY_NAMES,
    supported_languages=tuple(_LANGUAGE_DISPLAY_NAMES),
    span_specs=SPAN_SPECS,
    metric_specs=METRIC_SPECS,
    event_specs={},
    span_type_order=SPAN_TYPE_ORDER,
    metric_prefix="http.",
    classify_span=classify_span,
)
