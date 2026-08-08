# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Staging the content schemas weaver's policies read."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from genai_conformance import _advice_data

SCHEMA = json.dumps(
    {"$ref": "http://json-schema.org/draft-07/schema#"}, indent=2
)


@pytest.fixture(name="registry")
def _registry(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / "cache"))
    schemas = tmp_path / "model" / "gen-ai"
    schemas.mkdir(parents=True)
    (schemas / "gen-ai-tool-definitions.json").write_text(SCHEMA)
    return tmp_path / "model"


def test_the_unfetchable_ref_is_rewritten_in_the_staged_copy(
    registry,
) -> None:
    staged = Path(_advice_data(registry)).parent

    schema = (staged / "gen-ai-tool-definitions.json").read_text()
    assert json.loads(schema) == {"type": "object"}


def test_the_registry_is_left_alone(registry) -> None:
    _advice_data(registry)

    source = registry / "gen-ai" / "gen-ai-tool-definitions.json"
    assert source.read_text() == SCHEMA
