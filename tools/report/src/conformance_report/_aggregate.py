# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Join measured attributes to the pinned registry declarations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping

from opentelemetry.conformance import Domain
from opentelemetry.conformance import domain as load_domain

from ._discover import DATA_FILE, Target, discover
from ._types import Report, ReportTarget, Signal, Summary, Tally

# Read by ``docs/assets/data.js``, which checks it before rendering. Bump it
# for incompatible changes, and bump the copy there to match.
SCHEMA_VERSION = 1

GENERATED_BY = "otel-conformance-report build"

# The signal kinds a reduction records attributes for, mapped to the singular
# the report names one by. Entities are shaped differently and handled apart.
_SIGNAL_KINDS = {"spans": "span", "events": "event", "metrics": "metric"}

# See README.md for how requirement levels are counted.
SCORED_LEVELS: tuple[Literal["required", "recommended"], ...] = (
    "required",
    "recommended",
)


def _runner(target: Target) -> str:
    """Return the target's runner, or raise if no registry can be identified."""
    if target.runner is None:
        raise RuntimeError(
            f"{target.path} declares no `runner:`, so the report cannot tell "
            "what registry it was measured against"
        )
    return target.runner


def _domains(targets: Iterable[Target]) -> dict[str, Domain]:
    """Resolve one domain per runner named by the targets."""
    resolved: dict[str, Domain] = {}
    for target in targets:
        name = _runner(target)
        if name in resolved:
            continue
        found = load_domain(name)
        if found is None:
            raise RuntimeError(
                f"{target.path} names runner {name!r}, which exposes no "
                "DOMAIN, so the report cannot tell what registry it was "
                "measured against"
            )
        resolved[name] = found
    return resolved


def _coverage(
    declared: Mapping[str, str], emitted: Iterable[str]
) -> dict[str, Tally]:
    """Count declared and emitted attributes at each requirement level."""
    carried = set(emitted)
    counted: dict[str, Tally] = {}
    for attribute, level in declared.items():
        tally = counted.setdefault(level, {"emitted": 0, "declared": 0})
        tally["declared"] += 1
        if attribute in carried:
            tally["emitted"] += 1
    return dict(sorted(counted.items()))


def signal_coverage(
    data: Mapping[str, Any], model: Mapping[str, Any]
) -> list[Signal]:
    """Return per-signal coverage, leaving unknown declarations unscored."""
    built: list[Signal] = []
    for kind, singular in _SIGNAL_KINDS.items():
        for name, emitted in sorted(data.get(kind, {}).items()):
            entry: Signal = {
                "type": singular,
                "name": name,
                "emitted": sorted(emitted),
            }
            available: Mapping[str, Any] = model.get(kind, {})
            declared: Mapping[str, Any] = available.get(name) or {}
            attributes: Mapping[str, str] | None = declared.get("attributes")
            if attributes is None:
                entry["declared"] = None
                built.append(entry)
                continue
            entry["missing"] = sorted(set(attributes) - set(emitted))
            entry["coverage"] = _coverage(attributes, emitted)
            # Metrics and events are identified by name alone.
            if singular == "span":
                entry["identity"] = {
                    "attributes": sorted(emitted),
                    "span_kind": declared.get("kind"),
                }
            built.append(entry)
    return built


def _summary(signals: Iterable[Signal], findings: int = 0) -> Summary:
    """Sum scored coverage across signals and include the finding count."""
    totals: Summary = {
        "required": {"emitted": 0, "declared": 0},
        "recommended": {"emitted": 0, "declared": 0},
        "findings": findings,
    }
    for signal in signals:
        coverage = signal.get("coverage", {})
        for level in SCORED_LEVELS:
            if tally := coverage.get(level):
                totals[level]["emitted"] += tally["emitted"]
                totals[level]["declared"] += tally["declared"]
    return totals


def _referenced(
    declared: Mapping[str, Any], data: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Return model declarations referenced by the supplied reductions."""
    wanted: dict[str, set[str]] = {kind: set() for kind in _SIGNAL_KINDS}
    entities: set[str] = set()
    for reduction in data:
        for kind in _SIGNAL_KINDS:
            wanted[kind].update(reduction.get(kind, {}))
        entities.update(reduction.get("entities", {}))

    slice_: dict[str, Any] = {}
    for kind, names in wanted.items():
        available = declared.get(kind, {})
        slice_[kind] = {
            name: available[name]
            for name in sorted(names)
            if name in available
        }
    available_entities = declared.get("entities", {})
    slice_["entities"] = {
        name: available_entities[name]
        for name in sorted(entities)
        if name in available_entities
    }
    return slice_


def build(root: Path) -> Report:
    """Build a report from the measured targets under ``root``."""
    targets = discover(root)
    if not targets:
        raise RuntimeError(f"no conformance directories found under {root}")
    domains = _domains(targets)

    reductions = {
        target.id: json.loads(
            (target.directory / DATA_FILE).read_text(encoding="utf-8")
        )
        for target in targets
    }

    built: list[ReportTarget] = []
    for target in targets:
        data = reductions[target.id]
        found = domains[_runner(target)]
        signals = signal_coverage(data, found.coverage_model)
        built.append(
            {
                "id": target.id,
                "path": target.path,
                "domain": target.domain,
                "language": target.language,
                "side": target.side,
                "backend": target.backend,
                "runner": _runner(target),
                "instrumented_library": target.spec.instrumented_library,
                "instrumentation_library": (
                    target.spec.instrumentation_library
                ),
                "label": target.instrumentation,
                "scenario_classes": sorted(target.spec.scenarios),
                "signals": signals,
                "entities": data.get("entities", {}),
                "findings": data.get("findings", []),
                "summary": _summary(signals, len(data.get("findings", []))),
            }
        )

    registry: dict[str, Any] = {}
    for name, found in sorted(domains.items()):
        registry[name] = _referenced(
            found.coverage_model,
            [
                reductions[target.id]
                for target in targets
                if target.runner == name
            ],
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "domains": {
            name: {
                "registry_repo": found.repo,
                "registry_ref": found.ref,
                "registry_dir": found.registry_dir,
            }
            for name, found in sorted(domains.items())
        },
        "registry": registry,
        "targets": built,
    }


def render(document: Mapping[str, Any]) -> str:
    """Serialize a report with sorted keys and a trailing newline."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
