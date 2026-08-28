# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The report as a table, for a job summary or a pull request body."""

from __future__ import annotations

import collections
from typing import Any, Iterable, Mapping

from ._aggregate import SCORED_LEVELS

_ROWS = 15

# A registry ref that renames a signal moves every target at once. GitHub caps
# a job summary at 1 MiB and fails the step over it, taking the rebuild — and
# the pull request it would have opened — with it.
_CHANGES = 200


def _ratio(tally: Mapping[str, int] | None) -> str:
    if not tally or not tally.get("declared"):
        return "—"
    emitted, declared = tally["emitted"], tally["declared"]
    return f"{emitted}/{declared} ({emitted * 100 // declared}%)"


def _shortfall(target: Mapping[str, Any]) -> tuple[int, int]:
    """How badly a target wants looking at: gaps first, then findings."""
    summary = target.get("summary", {})
    missed = sum(
        summary.get(level, {}).get("declared", 0)
        - summary.get(level, {}).get("emitted", 0)
        for level in SCORED_LEVELS
    )
    return (-missed, -summary.get("findings", 0))


def render(document: Mapping[str, Any]) -> str:
    """A markdown summary of one report."""
    targets: list[Mapping[str, Any]] = list(document.get("targets", []))
    lines: list[str] = ["## Semantic-convention conformance", ""]

    languages = collections.Counter(t["language"] for t in targets)
    findings = collections.Counter(
        finding["id"]
        for t in targets
        for finding in t.get("findings", [])
        if "id" in finding
    )
    clean = sum(1 for t in targets if not t.get("findings"))

    lines += [
        f"{len(targets)} target{'' if len(targets) == 1 else 's'} across "
        + ", ".join(
            f"{count} {language}"
            for language, count in sorted(languages.items())
        )
        + f". {clean} with no findings, {sum(findings.values())} findings "
        f"of {len(findings)} kinds.",
        "",
    ]

    for name, pin in sorted(document.get("domains", {}).items()):
        lines.append(
            f"- `{name}` — {pin['registry_repo']} @ `{pin['registry_ref']}`"
        )
    lines.append("")

    lines += [
        "| Target | Instrumentation | Required | Recommended | Findings |",
        "| --- | --- | --- | --- | --- |",
    ]
    ranked = sorted(targets, key=_shortfall)
    for target in ranked[:_ROWS]:
        summary = target.get("summary", {})
        lines.append(
            "| `{id}` | `{library}` | {required} | {recommended} "
            "| {findings} |".format(
                id=target["id"],
                library=target["instrumentation_library"],
                required=_ratio(summary.get("required")),
                recommended=_ratio(summary.get("recommended")),
                findings=summary.get("findings", 0) or "—",
            )
        )
    if len(ranked) > _ROWS:
        lines.append("")
        lines.append(
            f"_{len(ranked) - _ROWS} further targets not shown; "
            "the full report is in `docs/data/conformance.json`._"
        )

    if findings:
        lines += ["", "<details><summary>Findings by kind</summary>", ""]
        lines += ["| Finding | Count |", "| --- | --- |"]
        for name, count in findings.most_common():
            lines.append(f"| `{name}` | {count} |")
        lines += ["", "</details>"]

    return "\n".join(lines) + "\n"


def render_diff(before: Mapping[str, Any], after: Mapping[str, Any]) -> str:
    """What changed between two reports, or nothing if they agree.

    Both halves of a coverage ratio, not only the numerator: moving a registry
    pin changes what the registry declares with no instrumentation having
    changed, and that denominator-only move is the whole reason the report is
    rebuilt when a pin moves. A diff that only compared emitted attributes
    would open that pull request with nothing to say. See the README.
    """

    def index(document: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        return {t["id"]: t for t in document.get("targets", [])}

    old, new = index(before), index(after)
    # First, so the cap below can never drop the change that explains the rest.
    changes: list[str] = list(_registry_diff(before, after))
    for target_id in sorted(set(old) | set(new)):
        if target_id not in old:
            changes.append(f"- added `{target_id}`")
            continue
        if target_id not in new:
            changes.append(f"- removed `{target_id}`")
            continue
        changes.extend(_target_diff(target_id, old[target_id], new[target_id]))
    if not changes:
        return ""
    shown, dropped = changes[:_CHANGES], len(changes) - _CHANGES
    if dropped > 0:
        shown.append(f"- _…and {dropped} further changes._")
    return "\n".join(["### Conformance changes", "", *shown]) + "\n"


def _registry_diff(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> Iterable[str]:
    """Which pin moved: one ref moves every denominator underneath it."""
    old: Mapping[str, Mapping[str, Any]] = before.get("domains", {})
    new: Mapping[str, Mapping[str, Any]] = after.get("domains", {})
    for name in sorted(set(old) | set(new)):
        was, now = old.get(name), new.get(name)
        if was == now:
            continue
        if now is None:
            yield f"- registry `{name}` removed"
            continue
        if was is None:
            yield f"- registry `{name}` added at `{now['registry_ref']}`"
            continue
        for field in ("registry_repo", "registry_ref", "registry_dir"):
            if was.get(field) != now.get(field):
                what = field.removeprefix("registry_")
                yield (
                    f"- registry `{name}` {what} `{was.get(field)}` → "
                    f"`{now.get(field)}`"
                )


def _signals(target: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {f"{s['type']} {s['name']}": s for s in target.get("signals", [])}


def _declared(signal: Mapping[str, Any]) -> dict[str, int] | None:
    """How many attributes each level declares: the ratio's denominator.

    ``None`` where the pinned registry declares nothing for the signal, which
    is "unknown" rather than "none" — the same distinction the report draws.
    """
    coverage: Mapping[str, Mapping[str, int]] | None = signal.get("coverage")
    if coverage is None:
        return None
    return {level: tally["declared"] for level, tally in coverage.items()}


def _signal_diff(
    target_id: str,
    signal: str,
    old: Mapping[str, Any],
    new: Mapping[str, Any],
) -> Iterable[str]:
    old_emitted = set(old.get("emitted", []))
    new_emitted = set(new.get("emitted", []))
    for attribute in sorted(new_emitted - old_emitted):
        yield f"- `{target_id}` `{signal}` **+** `{attribute}`"
    for attribute in sorted(old_emitted - new_emitted):
        yield f"- `{target_id}` `{signal}` **−** `{attribute}`"

    # A pin move can change what the registry declares without any run having
    # changed: the denominator moves on its own.
    was, now = _declared(old), _declared(new)
    if was is None and now is None:
        return
    if was is None or now is None:
        state = "now" if was is None else "no longer"
        yield f"- `{target_id}` `{signal}` {state} declared by the registry"
        return
    for level in sorted(set(was) | set(now)):
        if was.get(level, 0) != now.get(level, 0):
            yield (
                f"- `{target_id}` `{signal}` `{level}` declared "
                f"{was.get(level, 0)} → {now.get(level, 0)}"
            )


def _target_diff(
    target_id: str, old: Mapping[str, Any], new: Mapping[str, Any]
) -> Iterable[str]:
    was, now = _signals(old), _signals(new)
    for signal in sorted(set(was) | set(now)):
        before, after = was.get(signal), now.get(signal)
        # A signal appearing or going is one line, not one per attribute: a
        # renamed signal is every target at once, and the itemised form would
        # be most of the cap on its own.
        if before is None:
            yield f"- `{target_id}` `{signal}` **added**"
        elif after is None:
            yield f"- `{target_id}` `{signal}` **no longer emitted**"
        else:
            yield from _signal_diff(target_id, signal, before, after)

    before = collections.Counter(
        f["id"] for f in old.get("findings", []) if "id" in f
    )
    now = collections.Counter(
        f["id"] for f in new.get("findings", []) if "id" in f
    )
    for name in sorted(set(before) | set(now)):
        delta = now[name] - before[name]
        if delta:
            sign = "+" if delta > 0 else "−"
            yield f"- `{target_id}` finding `{name}` {sign}{abs(delta)}"
