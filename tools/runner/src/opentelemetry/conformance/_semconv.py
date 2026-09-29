# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The registry-shaped reduction of a run: what each signal carried.

The default reduction in :mod:`._coverage` keys spans by what a scenario
*declares*, which is all it can do without knowing the conventions. This one
reads the registry: every span is classified into a registry span type, and
the data file records, per type, which of that type's declared attributes were
present. Same for every event and metric the registry declares.

A domain supplies two things — a resolved coverage model and a way to
recognise its span types — and gets a ``build_data`` back.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

from ._report import ClassifySpan, Observed, finding_list, read

if TYPE_CHECKING:
    from ._spec import PackageSpec

BuildData = Callable[[Path, "PackageSpec"], object]


def semconv_coverage(
    classify: ClassifySpan, coverage_model: Callable[[], Mapping[str, Any]]
) -> BuildData:
    """A ``build_data`` reducing a run the way its registry reads it.

    ``coverage_model`` is a callable so a session can be built before the
    registry it needs has been fetched.
    """

    def build(report_dir: Path, spec: PackageSpec) -> object:
        if not report_dir.is_dir():
            raise RuntimeError(
                f"no weaver reports to reduce under {report_dir} — the run "
                "produced nothing to record"
            )
        return _reduce(read(report_dir, classify, spec), coverage_model())

    return build


def _reduce(
    observed: Observed, model: Mapping[str, Any]
) -> dict[str, object]:
    """A parsed run, reduced to the committed data-file shape.

    Every key is always there, empty or not: a run that emitted no metrics has
    to read back as that, and a signal an implementation stops emitting should
    show up as an empty object rather than a vanishing key.
    """
    return {
        # A span type is recognised by what it carried, so one with no
        # attributes is dropped; a bare event or metric still happened.
        "spans": _signals(observed.spans, model.get("spans", {}), bare=False),
        "events": _signals(observed.events, model.get("events", {})),
        "metrics": _signals(observed.metrics, model.get("metrics", {})),
        "entities": _entities(observed.resources, model.get("entities", {})),
        "findings": finding_list(observed.findings),
    }


def _signals(
    observed: Mapping[str, "set[str]"],
    declared: Mapping[str, Any],
    *,
    bare: bool = True,
) -> dict[str, list[str]]:
    """Which of each declared signal's attributes the run carried.

    Only signals the registry declares are recorded — anything else is not
    coverage of it, and shows up as a weaver finding instead.
    """
    recorded: dict[str, list[str]] = {}
    for name, carried in sorted(observed.items()):
        if name not in declared:
            continue
        present = sorted(declared[name]["attributes"].keys() & carried)
        if present or bare:
            recorded[name] = present
    return recorded


def _entities(
    resources: set[str],
    declared: Mapping[str, Any],
) -> dict[str, dict[str, list[str]]]:
    """Which of each declared entity's identity and description attributes the run carried on its resources.

    Only entities the registry declares are recorded — anything else is not
    coverage of it. An entity is recognised by its identifying attributes; only
    when all of its declared identifying attributes are present on a resource
    are its carried attributes recorded.
    """
    recorded: dict[str, dict[str, list[str]]] = {}
    for name, entity in sorted(declared.items()):
        identity = entity.get("identity", {})
        if not identity or not set(identity).issubset(resources):
            continue
        description = entity.get("description", {})
        recorded[name] = {
            "identity": sorted(identity.keys() & resources),
            "description": sorted(description.keys() & resources),
        }
    return recorded
