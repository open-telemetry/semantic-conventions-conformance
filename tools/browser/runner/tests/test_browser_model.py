# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The browser domain's registry and event-only coverage."""

import pytest

from browser_conformance import DOMAIN
from opentelemetry.conformance import WeaverNotInstalledError, check_weaver
from opentelemetry.conformance._runners import domain, load


def test_runner_resolves_to_the_browser_domain() -> None:
    assert load("browser-conformance") == DOMAIN.session
    assert domain("browser-conformance") is DOMAIN


def test_browser_events_do_not_credit_http_spans() -> None:
    assert not DOMAIN.classifier({})(
        "GET", "CLIENT", {"http.request.method": "GET"}
    )


@pytest.fixture(name="model", scope="module")
def _model():
    try:
        check_weaver()
    except WeaverNotInstalledError as error:
        pytest.skip(str(error))
    try:
        return DOMAIN.coverage_model
    except (OSError, RuntimeError) as error:
        pytest.skip(f"coverage model not available: {error}")


@pytest.mark.parametrize("event", ["exception", "browser.web_vital"])
def test_registry_declares_the_browser_event(model, event: str) -> None:
    assert event in model["events"]
