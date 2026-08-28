# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Every committed reduction, joined to what the registry declared.

A ``data.json`` records which of a signal's declared attributes a run carried;
the denominator is in the coverage model, which is a cache rather than a
committed file. Joining them here is what lets the site read the report
without weaver or a registry. See ``README.md``.

Output is deterministic — sorted keys, sorted sequences, no timestamp. The
committed file is compared byte-for-byte against a rebuild, and the ecosystem
registry downstream content-addresses what it ingests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from opentelemetry.conformance import Domain
from opentelemetry.conformance import domain as load_domain

from ._discover import DATA_FILE, Target, discover

SCHEMA_VERSION = 1

# The signal kinds a reduction records attributes for, mapped to the singular
# the report names one by. Entities are shaped differently and handled apart.
_SIGNAL_KINDS = {"spans": "span", "events": "event", "metrics": "metric"}

# The levels a score may be built from. The rest are counted, never scored:
# whether a condition held is not in the data, and an absent opt_in is correct
# behaviour. See the report's README.
SCORED_LEVELS = ("required", "recommended")


def _runner(target: Target) -> str:
    """The runner a target declared, which the report cannot do without.

    ``runner:`` is optional to the runner itself — a caller may supply the
    runners instead — but it is the only thing that names the registry the
    coverage denominator comes from. Without one there is nothing to score
    against, and a report published anyway would read as a target that
    declares nothing rather than as one that was never measured.
    """
    if target.runner is None:
        raise RuntimeError(
            f"{target.path} declares no `runner:` — the report cannot tell "
            "what registry it was measured against, so it has no denominator"
        )
    return target.runner


def _domains(targets: Iterable[Target]) -> dict[str, Domain]:
    """The domain behind each ``runner:`` the targets name.

    Resolved once per distinct runner: resolving one fetches a registry and
    runs weaver the first time.
    """
    resolved: dict[str, Domain] = {}
    for target in targets:
        name = _runner(target)
        if name in resolved:
            continue
        found = load_domain(name)
        if found is None:
            raise RuntimeError(
                f"{target.path} names runner {name!r}, which exposes no "
                "DOMAIN — the report cannot tell what registry it was "
                "measured against"
            )
        resolved[name] = found
    return resolved


def _coverage(
    declared: Mapping[str, str], emitted: Iterable[str]
) -> dict[str, dict[str, int]]:
    """Per requirement level, how much of it the run carried."""
    carried = set(emitted)
    counted: dict[str, dict[str, int]] = {}
    for attribute, level in declared.items():
        tally = counted.setdefault(level, {"emitted": 0, "declared": 0})
        tally["declared"] += 1
        if attribute in carried:
            tally["emitted"] += 1
    return dict(sorted(counted.items()))


def signal_coverage(
    data: Mapping[str, Any], model: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Each signal the run recorded, against what the registry declares.

    A signal the model does not declare keeps ``declared: null`` rather than
    scoring zero — only reachable when the report is built against a different
    pin than the data was, where the answer is "unknown", not "none".
    """
    built: list[dict[str, Any]] = []
    for kind, singular in _SIGNAL_KINDS.items():
        for name, emitted in sorted(data.get(kind, {}).items()):
            entry: dict[str, Any] = {
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
            # The identity the ecosystem explorer keys telemetry on. A span is
            # keyed by kind and attribute set — two shapes under one name are
            # two spans there. A metric or event is keyed by name alone, which
            # ``name`` above already carries: giving one an attribute set would
            # split two observations of the same metric into two identities.
            if singular == "span":
                entry["identity"] = {
                    "attributes": sorted(emitted),
                    "span_kind": declared.get("kind"),
                }
            built.append(entry)
    return built


def _summary(signals: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """One target's scored levels, summed over its signals."""
    totals = {level: {"emitted": 0, "declared": 0} for level in SCORED_LEVELS}
    for signal in signals:
        coverage: Mapping[str, Mapping[str, int]] = (
            signal.get("coverage") or {}
        )
        for level, tally in coverage.items():
            if level in totals:
                totals[level]["emitted"] += tally["emitted"]
                totals[level]["declared"] += tally["declared"]
    return totals


def _referenced(
    declared: Mapping[str, Any], data: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """The slice of one domain's model its targets actually referenced.

    The registries declare hundreds of signals; these scenarios touch a couple
    of dozen, and the whole model would be most of the file.
    """
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


def build(root: Path) -> dict[str, Any]:
    """The whole report: every target, and the registry it was read against."""
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

    built: list[dict[str, Any]] = []
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
                "runner": target.runner,
                "instrumented_library": target.spec.instrumented_library,
                "instrumentation_library": (
                    target.spec.instrumentation_library
                ),
                # The directory name: what tells two instrumentations of one
                # library apart where their coordinates do not. See
                # ``test_repo.py``.
                "label": target.instrumentation,
                "scenario_classes": sorted(target.spec.scenarios),
                "signals": signals,
                "entities": data.get("entities", {}),
                "findings": data.get("findings", []),
                "summary": {
                    **_summary(signals),
                    "findings": len(data.get("findings", [])),
                },
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
    """The report as it is committed: stable, and readable in a diff."""
    return json.dumps(document, indent=2, sort_keys=True) + "\n"
