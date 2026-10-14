# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The environment a scenario process runs with.

Everything a scenario needs — endpoints, placeholder keys, content capture —
arrives as environment variables, so nothing about the runner is tied to the
scenario's language. The real process environment wins over the declared
values, which is how a scenario gets pointed at a real provider: export a real
key and base URL and run it.
"""

from __future__ import annotations

import json
import logging
import os
from string import Template
from typing import Mapping, Sequence

_logger = logging.getLogger(__name__)

# Effectively infinite, so a periodic export can't split a scenario's metrics
# across reports — the flush at its end exports them. Passed as an environment
# variable so any language's SDK autoconfiguration picks it up.
METRIC_EXPORT_INTERVAL_MILLIS = 2**31 - 1

# Which scenario a one-shot process was started for, and the one action it is
# to perform.
SCENARIO_INDEX_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_INDEX"
SCENARIO_ACTION_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTION"

# The package's whole action table, readiness first. A process that answers
# actions rather than performing them — a measured server, a mock server, or a
# driver that starts one — needs every action the run may reach, not just the
# one it is currently on.
SCENARIO_ACTIONS_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_ACTIONS"

# The wire format the runner and a driven process speak, set only when the
# scenario contract's driver role made this run persistent. It is an
# internal handoff, not package configuration: a command is written once and
# learns from here whether it is being driven.
SCENARIO_PROTOCOL_VARIABLE = "OTEL_CONFORMANCE_SCENARIO_PROTOCOL"


def action_table_json(table: Sequence[Mapping[str, object]]) -> str:
    """The action table as the canonical JSON every language decodes."""
    return json.dumps(
        list(table),
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def timeout_seconds(variable: str, default: float) -> float:
    """A timeout, overridable through the environment.

    The defaults suit a laptop running one scenario; a loaded CI machine, a
    cold dependency install or a real provider behind a scenario can all need
    more, and none of those should need a code change. A value that isn't a
    positive number is reported and ignored rather than failing the run.
    """
    raw = os.environ.get(variable)
    if not raw:
        return default
    try:
        seconds = float(raw)
    except ValueError:
        seconds = 0
    if seconds <= 0:
        _logger.warning(
            "%s=%r is not a positive number of seconds; using %s",
            variable,
            raw,
            default,
        )
        return default
    return seconds


def build_env(
    *declared: Mapping[str, str], injected: Mapping[str, str]
) -> dict[str, str]:
    """Build a scenario process environment.

    Precedence, lowest first: each ``declared`` mapping in turn (package then
    scenario), the real process environment, then the runner's ``injected``
    values — those name the mock server and the collector this run actually
    started, so nothing may shadow them. Declared values may reference
    injected names as ``${NAME}``.
    """
    process_env = dict(os.environ)

    layered: dict[str, str] = {}
    for mapping in declared:
        layered.update(mapping)

    # The ambient environment wins — that is how a scenario is pointed at a
    # real provider — but say so, or a stray export looks like a code change.
    overridden = sorted(key for key in layered if key in process_env)
    if overridden:
        _logger.warning(
            "the process environment overrides declared value(s) for %s",
            ", ".join(overridden),
        )

    process_env.update(
        {
            key: Template(value).safe_substitute(injected)
            for key, value in layered.items()
            if key not in process_env
        }
    )
    process_env.update(injected)
    return process_env
