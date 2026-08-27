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


def test_the_registry_declares_the_span_types_we_classify(model) -> None:
    classified = DOMAIN.classifier(model)(
        "SELECT", "client", {"db.system.name": "postgresql"}
    )

    assert classified == {"db.client", "db.sql.client"}
    assert model["spans"]["db.client"]["kind"] == "client"
    assert model["spans"]["db.sql.client"]["kind"] == "client"


def test_the_general_type_declares_the_database_system(model) -> None:
    attributes = model["spans"]["db.client"]["attributes"]

    assert attributes["db.system.name"] == "required"


def test_the_sql_type_declares_query_text(model) -> None:
    attributes = model["spans"]["db.sql.client"]["attributes"]

    assert "db.query.text" in attributes


def test_the_registry_declares_operation_duration(model) -> None:
    metric = model["metrics"]["db.client.operation.duration"]

    assert metric["attributes"]["db.system.name"] == "required"
