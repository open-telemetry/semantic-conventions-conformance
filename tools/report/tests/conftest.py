# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A checkout small enough to assert on, laid out like the real one."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conformance_report import _aggregate

SPEC = """\
{runner}instrumented_library: {library}
instrumentation_library: {instrumentation}

scenarios:
{scenarios}
"""

# One span type, one metric, one entity, across every requirement level — so a
# test can tell a level that is scored from one that is only counted.
MODEL: dict[str, Any] = {
    "spans": {
        "demo.client": {
            "kind": "client",
            "attributes": {
                "demo.required": "required",
                "demo.also_required": "required",
                "demo.recommended": "recommended",
                "demo.conditional": "conditionally_required_conditional",
                "demo.optional": "opt_in",
            },
        }
    },
    "events": {"demo.event": {"attributes": {"demo.required": "required"}}},
    "metrics": {
        "demo.duration": {
            "attributes": {
                "demo.required": "required",
                "demo.recommended": "recommended",
            }
        }
    },
    "entities": {
        "service": {
            "identity": {"service.name": "required"},
            "description": {"service.version": "recommended"},
        }
    },
}


def write_target(
    root: Path,
    identifier: str,
    *,
    runner: str | None = "demo-conformance",
    library: str = "demo",
    instrumentation: str = "opentelemetry-demo",
    scenarios: tuple[str, ...] = ("main",),
    data: dict[str, Any] | None = None,
) -> Path:
    """One conformance directory under ``root/scenarios/<identifier>``.

    ``runner=None`` leaves the key out, which the spec allows and the report
    does not.
    """
    directory = root / "scenarios" / identifier
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "conformance.yaml").write_text(
        SPEC.format(
            runner="" if runner is None else f"runner: {runner}\n",
            library=library,
            instrumentation=instrumentation,
            scenarios="\n".join(
                f'  {name}:\n    run: "true"' for name in scenarios
            ),
        ),
        encoding="utf-8",
    )
    (directory / "data.json").write_text(
        json.dumps(
            data
            if data is not None
            else {
                "spans": {
                    "demo.client": ["demo.required", "demo.recommended"]
                },
                "events": {},
                "metrics": {},
                "entities": {},
                "findings": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return directory


@pytest.fixture
def one_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the wrapper a `runner:` would resolve to.

    Resolving the real thing fetches a registry and runs weaver.
    """

    class Stub:
        name = "demo-conformance"
        repo = "open-telemetry/demo"
        ref = "v1.0.0"
        registry_dir = "model"
        coverage_model = MODEL

    monkeypatch.setattr(_aggregate, "load_domain", lambda _name: Stub())
