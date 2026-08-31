# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The shared workload and runner support the same database backends."""

import json
from pathlib import Path

from database_conformance import _BACKENDS


def test_contract_covers_every_runner_backend() -> None:
    contract = Path(__file__).parents[2] / "test-client" / "contract.json"
    document = json.loads(contract.read_text(encoding="utf-8"))

    assert set(document["backends"]) == set(_BACKENDS)
