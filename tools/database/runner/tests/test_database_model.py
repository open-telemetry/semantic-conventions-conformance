# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""What the pinned database registry resolves to."""

from __future__ import annotations

import pytest

from database_conformance import DOMAIN
from opentelemetry.conformance import WeaverNotInstalledError, check_weaver


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


@pytest.mark.parametrize(
    ("system", "span_type"),
    [
        ("mariadb", "db.mariadb.client"),
        ("postgresql", "db.postgresql.client"),
    ],
)
def test_the_registry_declares_the_span_types_we_classify(
    model, system: str, span_type: str
) -> None:
    classified = DOMAIN.classifier(model)(
        "SELECT", "client", {"db.system.name": system}
    )

    assert classified == {span_type}
    assert model["spans"][span_type]["kind"] == "client"
    attributes = model["spans"][span_type]["attributes"]
    assert attributes["db.system.name"] == "required"
    assert "db.query.text" in attributes


def test_the_registry_declares_operation_duration(model) -> None:
    metric = model["metrics"]["db.client.operation.duration"]

    assert metric["attributes"]["db.system.name"] == "required"
