# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Every SQL contract backend is available from the database runner."""

import json
from pathlib import Path

from database_conformance import _BACKENDS


def test_runner_supports_every_sql_contract_backend() -> None:
    contract = Path(__file__).parents[2] / "sql-test-client" / "contract.json"
    document = json.loads(contract.read_text(encoding="utf-8"))

    assert set(document["backends"]) <= set(_BACKENDS)
