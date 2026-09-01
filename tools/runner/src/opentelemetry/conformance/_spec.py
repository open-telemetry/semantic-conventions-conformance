# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``conformance.yaml`` → frozen dataclasses.

Keys are validated strictly: an unknown or misspelled key raises instead of
silently weakening the check it was meant to tighten.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence, cast

import yaml

SPEC_FILE = "conformance.yaml"
_SCENARIO_CONTRACT_KEYS = ("spans", "metrics", "events")


class SpecError(ValueError):
    """The package's ``conformance.yaml`` is invalid."""


@dataclass(frozen=True)
class AttributeMatcher:
    """One expectation about an attribute across the matched spans."""

    equals: object | None = None
    present: bool | None = None
    distinct: int | None = None

    def describe(self) -> str:
        if self.present is not None:
            return f"present={self.present}"
        if self.distinct is not None:
            return f"{self.distinct} distinct values"
        return f"== {self.equals!r}"


@dataclass(frozen=True)
class SpanMatch:
    """What selects a span — every declared facet has to hold.

    Facets are named rather than flattened into one namespace so selecting on
    something that isn't an attribute (the span kind, later its status or
    parent) doesn't collide with an attribute of the same name.
    """

    attributes: Mapping[str, object]
    kind: str | None = None
    type: str | None = None

    def key(self) -> str:
        """A stable identifier for what this selects.

        JSON rather than a joined string: a value containing the separator
        would otherwise read back as a different selection — or collide with
        one. Used to group and order, never written out.
        """
        return json.dumps(
            dict(sorted(self._facets(), key=lambda facet: facet[0])),
            sort_keys=True,
            separators=(",", ":"),
            default=repr,
        )

    def as_dict(self) -> dict[str, object]:
        """This selection the way ``conformance.yaml`` writes it."""
        selection: dict[str, object] = {}
        if self.attributes:
            selection["attributes"] = dict(sorted(self.attributes.items()))
        if self.kind is not None:
            selection["kind"] = self.kind
        if self.type is not None:
            selection["type"] = self.type
        return selection

    def describe(self) -> str:
        return ", ".join(f"{key}={value!r}" for key, value in self._facets())

    def _facets(self) -> list[tuple[str, object]]:
        facets: list[tuple[str, object]] = list(self.attributes.items())
        if self.kind is not None:
            facets.append(("kind", self.kind))
        if self.type is not None:
            facets.append(("type", self.type))
        return facets


@dataclass(frozen=True)
class SpanExpectation:
    """How many spans ``match`` selects, and what they must carry.

    The two halves are declared separately — ``match`` selects, ``expect``
    asserts — so an attribute used to find a span reads differently from one
    being checked on it. Every span in the report must be selected by some
    expectation, keeping the check exact when assertions are present.
    """

    match: SpanMatch
    count: int | None = None
    attributes: Mapping[str, AttributeMatcher] = field(
        default_factory=dict[str, AttributeMatcher]
    )

    def describe(self) -> str:
        return self.match.describe()


@dataclass(frozen=True)
class ExpectedViolation:
    """One known-and-accepted semconv violation, or a class of them.

    Matched on weaver's advice ``id`` plus the full ``context`` — a substring
    of the message can match a different finding. ``signal_name`` is
    deliberately not matched: it embeds run-specific detail, such as the span
    name a GenAI finding was raised on.

    ``context`` is optional, and leaving it out accepts *every* finding with
    that ``id`` — the right shape when the findings are one gap seen many
    times, and the wrong one otherwise, because a declaration matching a whole
    class stops reporting when the class shrinks. It still fails once the
    class empties, which keeps suppressions from outliving the gap.
    """

    id: str
    context: Mapping[str, object] | None
    reason: str

    def describe(self) -> str:
        if self.context is None:
            return f"[{self.id}] any context"
        return f"[{self.id}] context={dict(self.context)!r}"


@dataclass(frozen=True)
class ScenarioSpec:
    """One scenario's expectations.

    ``spans``, ``metrics`` and ``events`` are ``None`` when the scenario
    doesn't declare them, which means "not checked" — a scenario with no
    expectations at all only has to run and stay free of semconv violations.
    Declaring one makes its check exact.

    ``expected_violations`` are this scenario's own and are checked both ways:
    reported, they pass; no longer reported, the run says to remove them.
    ``inherited_violations`` come from the package and only ever suppress —
    a gap the package declares because it is everywhere shouldn't fail the one
    scenario that happens not to reach it.
    """

    name: str
    directory: Path
    env: Mapping[str, str]
    run: tuple[str, ...]
    spans: tuple[SpanExpectation, ...] | None
    metrics: tuple[str, ...] | None
    events: tuple[str, ...] | None
    expected_violations: tuple[ExpectedViolation, ...]
    inherited_violations: tuple[ExpectedViolation, ...] = ()


@dataclass(frozen=True)
class WeaverSpec:
    """Which registry weaver validates against, and with which policies.

    Every field is optional so a package declares only what differs from the
    defaults its runner supplies. Relative paths resolve against the package
    directory; values may reference injected variables as ``${NAME}``, since a
    registry is often provisioned at run time rather than committed.
    """

    registry: str | None = None
    policies: str | None = None
    advice_data: str | None = None
    config: str | None = None

    def over(self, defaults: WeaverSpec) -> WeaverSpec:
        """This spec's fields, falling back to ``defaults`` field by field."""
        return WeaverSpec(
            registry=self.registry or defaults.registry,
            policies=self.policies or defaults.policies,
            advice_data=self.advice_data or defaults.advice_data,
            config=self.config or defaults.config,
        )


DEFAULT_HEALTH_PATH = "/health"
DEFAULT_URL_VAR = "MOCK_SERVER_URL"


@dataclass(frozen=True)
class ServerSpec:
    """A server started for the session, reachable by the scenarios.

    ``run`` is told which port to listen on through ``${PORT}``, and its base
    URL is published to the scenarios as ``${<url_var>}``. It inherits this
    process's environment; anything else it needs it carries itself, e.g.
    ``env VAR=value the-server --port ${PORT}``.

    Every field is ``None`` until declared, so a package can override one of
    them — a different health endpoint for the runner's server, say — without
    restating the rest. Read the resolved values through
    :attr:`health_path` and :attr:`url_variable`.
    """

    run: tuple[str, ...] | None = None
    health: str | None = None
    url_var: str | None = None

    @property
    def health_path(self) -> str:
        return self.health or DEFAULT_HEALTH_PATH

    @property
    def url_variable(self) -> str:
        return self.url_var or DEFAULT_URL_VAR

    def over(self, defaults: ServerSpec) -> ServerSpec:
        """This spec's fields, falling back to ``defaults`` field by field."""
        return ServerSpec(
            run=self.run or defaults.run,
            health=self.health or defaults.health,
            url_var=self.url_var or defaults.url_var,
        )


@dataclass(frozen=True)
class PackageSpec:
    instrumented_library: str
    instrumentation_library: str
    directory: Path
    env: Mapping[str, str]
    weaver: WeaverSpec
    server: ServerSpec
    setup: tuple[str, ...] | None
    scenarios: Mapping[str, ScenarioSpec]
    # Also merged into every scenario as ``inherited_violations``.
    expected_violations: tuple[ExpectedViolation, ...] = ()
    # Which wrapper supplies the registry and the reduction (see
    # :mod:`._runners`). None means the caller supplies all available runners.
    runner: str | None = None
    runner_config: Mapping[str, object] = field(
        default_factory=dict[str, object]
    )


def _require_mapping(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SpecError(
            f"{where}: expected a mapping, got {type(value).__name__}"
        )
    return cast("Mapping[str, object]", value)


def _require_list(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise SpecError(
            f"{where}: expected a list, got {type(value).__name__}"
        )
    return cast("list[object]", value)


def _check_keys(
    mapping: Mapping[str, object], allowed: Sequence[str], where: str
) -> None:
    unknown = sorted(set(mapping) - set(allowed))
    if unknown:
        raise SpecError(
            f"{where}: unknown key(s) {unknown}; allowed: {sorted(allowed)}"
        )


def _optional_string(
    mapping: Mapping[str, object], key: str, where: str
) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise SpecError(f"{where}.{key}: expected a non-empty string")
    return value


def _required_string(
    mapping: Mapping[str, object], key: str, where: str
) -> str:
    value = _optional_string(mapping, key, where)
    if value is None:
        raise SpecError(f"{where}.{key} is required")
    return value


def _parse_command(value: object, where: str) -> tuple[str, ...]:
    """A command is a shell-style string, or an already-split list."""
    if isinstance(value, str):
        return tuple(shlex.split(value))
    return _parse_string_list(value, f"{where} (a command string or list)")


def _parse_matcher(value: object, where: str) -> AttributeMatcher:
    if not isinstance(value, Mapping):
        return AttributeMatcher(equals=value)

    matcher = cast("Mapping[str, object]", value)
    _check_keys(matcher, ("present", "distinct"), where)
    if len(matcher) != 1:
        raise SpecError(f"{where}: expected exactly one of present/distinct")
    if "present" in matcher:
        present = matcher["present"]
        if not isinstance(present, bool):
            raise SpecError(f"{where}: present must be a boolean")
        return AttributeMatcher(present=present)
    distinct = matcher["distinct"]
    if not isinstance(distinct, int) or isinstance(distinct, bool):
        raise SpecError(f"{where}: distinct must be an integer")
    return AttributeMatcher(distinct=distinct)


def _parse_match(value: object, where: str) -> SpanMatch:
    match = _require_mapping(value or {}, where)
    _check_keys(match, ("attributes", "kind", "type"), where)
    attributes = _require_mapping(
        match.get("attributes") or {}, f"{where}.attributes"
    )
    if not attributes and "kind" not in match:
        raise SpecError(f"{where}: declare at least one thing to match on")
    return SpanMatch(
        attributes=dict(attributes),
        kind=_optional_string(match, "kind", where),
        type=_optional_string(match, "type", where),
    )


def _parse_span(value: object, where: str) -> SpanExpectation:
    span = _require_mapping(value, where)
    _check_keys(span, ("match", "expect"), where)
    if "match" not in span:
        raise SpecError(f"{where}: match is required")

    match = _parse_match(span["match"], f"{where}.match")
    if "expect" not in span:
        return SpanExpectation(match=match)

    expect = _require_mapping(span["expect"], f"{where}.expect")
    _check_keys(expect, ("count", "attributes"), f"{where}.expect")
    count = expect.get("count")
    if not isinstance(count, int) or isinstance(count, bool):
        raise SpecError(
            f"{where}.expect: count is required and must be an integer"
        )
    attributes = _require_mapping(
        expect.get("attributes") or {}, f"{where}.expect.attributes"
    )
    return SpanExpectation(
        match=match,
        count=count,
        attributes={
            name: _parse_matcher(matcher, f"{where}.expect.attributes.{name}")
            for name, matcher in attributes.items()
        },
    )


def _parse_violation(value: object, where: str) -> ExpectedViolation:
    violation = _require_mapping(value, where)
    _check_keys(violation, ("id", "context", "reason"), where)
    # Absent and empty are different: `context: {}` still means "the finding
    # carried no context", while leaving it out accepts any context.
    context = (
        dict(_require_mapping(violation["context"], f"{where}.context"))
        if "context" in violation
        else None
    )
    return ExpectedViolation(
        id=_required_string(violation, "id", where),
        context=context,
        reason=_required_string(violation, "reason", where),
    )


def _parse_env(value: object, where: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for name, entry in _require_mapping(value or {}, where).items():
        if not isinstance(entry, str):
            raise SpecError(
                f"{where}.{name}: environment values must be strings — quote "
                f"{entry!r}"
            )
        parsed[name] = entry
    return parsed


def _parse_weaver(value: object, where: str) -> WeaverSpec:
    weaver = _require_mapping(value or {}, where)
    _check_keys(
        weaver, ("registry", "policies", "advice_data", "config"), where
    )
    return WeaverSpec(
        registry=_optional_string(weaver, "registry", where),
        policies=_optional_string(weaver, "policies", where),
        advice_data=_optional_string(weaver, "advice_data", where),
        config=_optional_string(weaver, "config", where),
    )


def _parse_server(value: object, where: str) -> ServerSpec:
    server = _require_mapping(value or {}, where)
    _check_keys(server, ("run", "health", "url_var"), where)
    return ServerSpec(
        run=_parse_command(server["run"], f"{where}.run")
        if "run" in server
        else None,
        health=_optional_string(server, "health", where),
        url_var=_optional_string(server, "url_var", where),
    )


def _parse_string_list(value: object, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    items = _require_list(value, where)
    if not all(isinstance(item, str) for item in items):
        raise SpecError(f"{where}: expected a list of strings")
    return tuple(cast("list[str]", items))


def _parse_scenario(
    name: str,
    value: object,
    directory: Path,
    where: str,
    *,
    inherited: tuple[ExpectedViolation, ...] = (),
) -> ScenarioSpec:
    scenario = _require_mapping(value or {}, where)
    _check_keys(
        scenario,
        ("env", "run", "spans", "metrics", "events", "expected_violations"),
        where,
    )
    spans = (
        _require_list(scenario["spans"] or [], f"{where}.spans")
        if "spans" in scenario
        else None
    )
    violations = _require_list(
        scenario.get("expected_violations") or [],
        f"{where}.expected_violations",
    )
    if "run" not in scenario:
        raise SpecError(
            f"{where}: run is required — name the command that runs this "
            "scenario, e.g. 'otel-conformance-python <scenario>.py'"
        )
    own = tuple(
        _parse_violation(violation, f"{where}.expected_violations[{index}]")
        for index, violation in enumerate(violations)
    )
    if clashing := {v.id for v in own} & {v.id for v in inherited}:
        raise SpecError(
            f"{where}.expected_violations: {sorted(clashing)} is already "
            "declared for every scenario at the top level — remove one of "
            "the two"
        )
    return ScenarioSpec(
        name=name,
        directory=directory,
        env=_parse_env(scenario.get("env"), f"{where}.env"),
        run=_parse_command(scenario["run"], f"{where}.run"),
        spans=None
        if spans is None
        else tuple(
            _parse_span(span, f"{where}.spans[{index}]")
            for index, span in enumerate(spans)
        ),
        metrics=_parse_string_list(scenario["metrics"], f"{where}.metrics")
        if "metrics" in scenario
        else None,
        events=_parse_string_list(scenario["events"], f"{where}.events")
        if "events" in scenario
        else None,
        expected_violations=own,
        inherited_violations=inherited,
    )


def _load_scenario_contract(
    directory: Path, value: object, where: str
) -> Mapping[str, object]:
    contract = _required_string(
        {"scenario_contract": value}, "scenario_contract", where
    )
    path = directory / contract
    if not path.is_file():
        raise SpecError(f"{path} not found")

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document = _require_mapping(document or {}, str(path))
    _check_keys(document, ("scenarios",), str(path))
    scenarios = _require_mapping(
        document.get("scenarios") or {}, f"{path}.scenarios"
    )
    if not scenarios:
        raise SpecError(f"{path}: declares no scenarios")

    for name, value in scenarios.items():
        scenario = _require_mapping(value or {}, f"{path}.scenarios.{name}")
        _check_keys(
            scenario,
            _SCENARIO_CONTRACT_KEYS,
            f"{path}.scenarios.{name}",
        )
    return scenarios


def _merge_scenarios(
    contract: Mapping[str, object], declared: Mapping[str, object], path: Path
) -> Mapping[str, object]:
    merged = {
        name: dict(_require_mapping(value or {}, f"{path}.scenarios.{name}"))
        for name, value in contract.items()
    }
    for name, value in declared.items():
        scenario = dict(
            _require_mapping(value or {}, f"{path}.scenarios.{name}")
        )
        merged[name] = {**merged.get(name, {}), **scenario}
    return merged


def load_spec(directory: Path) -> PackageSpec:
    """Load ``<directory>/conformance.yaml``."""
    path = directory / SPEC_FILE
    if not path.is_file():
        raise SpecError(f"{path} not found")

    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document = _require_mapping(document or {}, str(path))
    _check_keys(
        document,
        (
            "runner",
            "runner_config",
            "scenario_contract",
            "instrumented_library",
            "instrumentation_library",
            "env",
            "weaver",
            "server",
            "setup",
            "scenarios",
            "expected_violations",
        ),
        str(path),
    )

    instrumented = _required_string(
        document, "instrumented_library", str(path)
    )
    instrumentation = _required_string(
        document, "instrumentation_library", str(path)
    )

    local_scenarios = _require_mapping(
        document.get("scenarios") or {}, f"{path}.scenarios"
    )
    contract_scenarios: Mapping[str, object]
    if "scenario_contract" in document:
        contract_scenarios = _load_scenario_contract(
            directory,
            document["scenario_contract"],
            str(path),
        )
    else:
        contract_scenarios = {}
    declared = _merge_scenarios(contract_scenarios, local_scenarios, path)
    if not declared:
        raise SpecError(f"{path}: declares no scenarios")

    inherited = tuple(
        _parse_violation(violation, f"{path}.expected_violations[{index}]")
        for index, violation in enumerate(
            _require_list(
                document.get("expected_violations") or [],
                f"{path}.expected_violations",
            )
        )
    )

    return PackageSpec(
        instrumented_library=instrumented,
        instrumentation_library=instrumentation,
        directory=directory,
        runner=_optional_string(document, "runner", str(path)),
        runner_config=dict(
            _require_mapping(
                document["runner_config"], f"{path}.runner_config"
            )
        )
        if "runner_config" in document
        else {},
        env=_parse_env(document.get("env"), f"{path}.env"),
        weaver=_parse_weaver(document.get("weaver"), f"{path}.weaver"),
        server=_parse_server(document.get("server"), f"{path}.server"),
        setup=_parse_command(document["setup"], f"{path}.setup")
        if "setup" in document
        else None,
        expected_violations=inherited,
        scenarios={
            name: _parse_scenario(
                name,
                scenario,
                directory,
                f"{path}.scenarios.{name}",
                inherited=inherited,
            )
            for name, scenario in declared.items()
        },
    )


def scenarios(directory: Path) -> list[str]:
    """Scenario names declared by the package, in declaration order."""
    return list(load_spec(Path(directory)).scenarios)


def declared_runner(directory: Path) -> str | None:
    """The wrapper ``directory`` names, without validating the rest of it.

    Read on its own because the wrapper is what supplies the registry, and a
    package with no registry doesn't load — so which wrapper to open it with
    has to be answerable before the file is fully parsed.
    """
    path = Path(directory) / SPEC_FILE
    if not path.is_file():
        raise SpecError(f"{path} not found")
    document = _require_mapping(
        yaml.safe_load(path.read_text(encoding="utf-8")) or {}, str(path)
    )
    return _optional_string(document, "runner", str(path))
