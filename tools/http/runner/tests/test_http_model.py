# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""What the pinned upstream registry resolves to.

Classification names span types by hand; the registry declares them. Nothing
else checks the two still agree, and an upstream restructure would otherwise
show up as a data.json that quietly went empty.

Needs the pinned registry and the model resolved out of it.
"""

from __future__ import annotations

import pytest

from http_conformance import DOMAIN
from opentelemetry.conformance import WeaverNotInstalledError, check_weaver


@pytest.fixture(name="model", scope="module")
def _model():
    # Checked before touching the model, because reaching for it fetches the
    # registry first — a download this test would then skip without using.
    try:
        check_weaver()
    except WeaverNotInstalledError as error:
        pytest.skip(str(error))
    try:
        return DOMAIN.coverage_model
    except (OSError, RuntimeError) as error:
        pytest.skip(f"coverage model not available: {error}")


@pytest.mark.parametrize(
    ("kind", "span_type"),
    [("client", "http.client"), ("server", "http.server")],
)
def test_the_registry_declares_the_span_type_we_classify_as(
    model, kind: str, span_type: str
) -> None:
    classified = DOMAIN.classifier(model)(
        "GET", kind, {"http.request.method": "GET"}
    )

    assert classified == {span_type}
    assert span_type in model["spans"]
    assert model["spans"][span_type]["kind"] == kind


def test_the_registry_still_requires_what_the_policy_flags(model) -> None:
    """The policy hard-codes these; the registry is where they come from."""
    levels = model["spans"]["http.server"]["attributes"]

    assert levels["http.request.method"] == "required"
    assert levels["url.path"] == "required"
    assert levels["url.scheme"] == "required"
