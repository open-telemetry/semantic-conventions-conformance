# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""What a domain wires in when the caller brings their own registry."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from opentelemetry.conformance import Domain, _domain
from opentelemetry.conformance._report import ClassifySpan


def classifier(model: object) -> ClassifySpan:
    del model
    return lambda span: ()


@pytest.fixture(name="domain")
def _domain_fixture(tmp_path, monkeypatch):
    """A domain whose pin can't be fetched, so a fetch fails the test."""
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / "cache"))

    def unreachable(*args: object, **kwargs: object) -> Path:
        raise AssertionError("the pinned registry was fetched")

    monkeypatch.setattr(_domain, "provision", unreachable)

    def build(advice_data: Callable[[Path], str] | None = None) -> Domain:
        return Domain(
            name="test-conformance",
            repo="open-telemetry/semantic-conventions",
            ref="deadbeef",
            classifier=classifier,
            advice_data=advice_data,
        )

    return build


def test_a_caller_registry_is_used_without_fetching_the_pin(
    domain, tmp_path
) -> None:
    local = tmp_path / "working-tree" / "model"

    assert domain().weaver_defaults(local).registry == str(local)


def test_advice_data_is_read_from_the_registry_in_use(
    domain, tmp_path
) -> None:
    seen: list[Path] = []
    local = tmp_path / "working-tree" / "model"

    def advice_data(registry: Path) -> str:
        seen.append(registry)
        return str(registry / "*.json")

    defaults = domain(advice_data).weaver_defaults(local)

    assert seen == [local]
    assert defaults.advice_data == str(local / "*.json")
