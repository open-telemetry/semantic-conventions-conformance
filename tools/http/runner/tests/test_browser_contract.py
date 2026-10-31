# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from dataclasses import replace
from pathlib import Path

import pytest

from opentelemetry.conformance import load_spec


@pytest.mark.parametrize(
    "browser_client",
    [
        "fetch/opentelemetry-fetch/client",
        "xml-http-request/opentelemetry-xml-http-request/client",
    ],
)
def test_browser_client_uses_the_shared_http_contract(
    browser_client: str,
) -> None:
    root = Path(__file__).resolve().parents[4] / "scenarios/http/js"
    reference = load_spec(root / "undici/opentelemetry-undici/client")
    browser = load_spec(root / browser_client)

    assert browser.scenarios.keys() == reference.scenarios.keys()
    for name, scenario in browser.scenarios.items():
        expected = reference.scenarios[name]
        assert replace(scenario, directory=expected.directory) == expected
