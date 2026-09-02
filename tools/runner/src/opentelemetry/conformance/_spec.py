# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``conformance.yaml`` → frozen dataclasses.

Keys are validated strictly: an unknown or misspelled key raises instead of
silently weakening the check it was meant to tighten.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Mapping, Sequence, cast

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
class ScenarioRunSpec:
    """How the runner communicates with a scenario command."""

    command: tuple[str, ...]
    protocol: Literal["jsonl-v1"] | None = None

    @property
    def one_shot(self) -> bool:
        """Whether each selected action starts a new process."""
        return self.protocol is None


@dataclass(frozen=True)
class ScenarioSpec:
    """One scenario's expectations.

    ``spans``, ``metrics`` and ``events`` are ``None`` when the scenario
    doesn't declare them, which means "not checked". Declaring one makes its
    check exact. ``optional_metrics`` names what an implementation records
    only for some of its actions: emitting one is never undeclared, and
    never emitting it is never missing.
    """

    name: str
    directory: Path
    env: Mapping[str, str]
    run: tuple[str, ...]
    spans: tuple[SpanExpectation, ...] | None
    metrics: tuple[str, ...] | None
    events: tuple[str, ...] | None
    description: str = ""
    index: int | None = None
    action: Mapping[str, object] | None = None
    protocol: Literal["jsonl-v1"] | None = None
    optional_metrics: tuple[str, ...] = ()

    @property
    def run_spec(self) -> ScenarioRunSpec:
        """The command and its selected process protocol."""
        return ScenarioRunSpec(self.run, self.protocol)

    @property
    def display_name(self) -> str:
        """A human label that keeps an indexed scenario unambiguous."""
        description = self.description or self.name
        if self.index is None:
            return description
        return f"[{self.index}] {description}"


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
    action_table: tuple[Mapping[str, object], ...] = ()
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
        command = tuple(shlex.split(value))
    else:
        command = _parse_string_list(
            value, f"{where} (a command string or list)"
        )
    if not command:
        raise SpecError(f"{where}: expected a non-empty command")
    return command


def _parse_scenario_run(value: object, where: str) -> ScenarioRunSpec:
    if not isinstance(value, Mapping):
        return ScenarioRunSpec(_parse_command(value, where))

    run = cast("Mapping[str, object]", value)
    _check_keys(run, ("command", "protocol"), where)
    if "command" not in run:
        raise SpecError(f"{where}.command is required")
    protocol = _required_string(run, "protocol", where)
    if protocol != "jsonl-v1":
        raise SpecError(
            f"{where}.protocol: unknown protocol {protocol!r}; "
            "allowed: ['jsonl-v1']"
        )
    return ScenarioRunSpec(
        command=_parse_command(run["command"], f"{where}.command"),
        protocol="jsonl-v1",
    )


def _parse_action(value: object, where: str) -> Mapping[str, object]:
    action = _require_mapping(value, where)
    if not action:
        raise SpecError(f"{where}: expected a non-empty mapping")

    def check_keys(entry: object, location: str) -> None:
        if isinstance(entry, Mapping):
            mapping = cast("Mapping[object, object]", entry)
            for key, child in mapping.items():
                if not isinstance(key, str):
                    raise SpecError(
                        f"{location}: action mapping keys must be strings"
                    )
                check_keys(child, f"{location}.{key}")
        elif isinstance(entry, list):
            items = cast("list[object]", entry)
            for index, child in enumerate(items):
                check_keys(child, f"{location}[{index}]")

    check_keys(action, where)
    try:
        json.dumps(action, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise SpecError(
            f"{where}: action must be represented as JSON: {error}"
        ) from error
    return action


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


def _parse_additional_metrics(
    value: object, where: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split the package's extra metrics into required and optional ones.

    A bare name is recorded by every action, so it joins the exact check.
    ``{name: ..., required: false}`` is recorded by only some of them —
    a request body size, say — which no flat list of names can say.
    """
    required: list[str] = []
    optional: list[str] = []
    for index, item in enumerate(_require_list(value or [], where)):
        position = f"{where}[{index}]"
        if isinstance(item, str):
            required.append(item)
            continue
        entry = _require_mapping(item, position)
        _check_keys(entry, ("name", "required"), position)
        name = _required_string(entry, "name", position)
        is_required = entry.get("required", True)
        if not isinstance(is_required, bool):
            raise SpecError(f"{position}.required: expected a boolean")
        (required if is_required else optional).append(name)
    return tuple(required), tuple(optional)


def _with_package_additions(
    scenario: ScenarioSpec,
    additional_metrics: Sequence[str],
    optional_metrics: Sequence[str],
    additional_spans: Sequence[SpanExpectation],
) -> ScenarioSpec:
    """Join what only this implementation emits onto one scenario.

    A scenario that declares nothing of a kind stays unchecked, so nothing
    the package adds turns an unchecked kind into a checked one.
    """
    metrics = (
        scenario.metrics
        if scenario.metrics is None or not additional_metrics
        else tuple(sorted({*scenario.metrics, *additional_metrics}))
    )
    spans = (
        scenario.spans
        if scenario.spans is None or not additional_spans
        else (*scenario.spans, *additional_spans)
    )
    return replace(
        scenario,
        metrics=metrics,
        spans=spans,
        optional_metrics=(
            tuple(sorted({*scenario.optional_metrics, *optional_metrics}))
            if scenario.metrics is not None
            else scenario.optional_metrics
        ),
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
    description: str | None = None,
    index: int | None = None,
    action: Mapping[str, object] | None = None,
    run_spec: ScenarioRunSpec | None = None,
) -> ScenarioSpec:
    scenario = _require_mapping(value or {}, where)
    _check_keys(
        scenario,
        ("env", "run", "spans", "metrics", "events"),
        where,
    )
    spans = (
        _require_list(scenario["spans"] or [], f"{where}.spans")
        if "spans" in scenario
        else None
    )
    if "run" not in scenario and run_spec is None:
        raise SpecError(
            f"{where}: run is required — name the command that runs this "
            "scenario, e.g. 'otel-conformance-python <scenario>.py'"
        )
    parsed_run = (
        _parse_scenario_run(scenario["run"], f"{where}.run")
        if run_spec is None
        else run_spec
    )
    return ScenarioSpec(
        name=name,
        directory=directory,
        env=_parse_env(scenario.get("env"), f"{where}.env"),
        run=parsed_run.command,
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
        description=description or name,
        index=index,
        action=action,
        protocol=parsed_run.protocol,
    )


def _load_scenario_contract(
    directory: Path, value: object, where: str
) -> tuple[Path, object]:
    contract = _required_string(
        {"scenario_contract": value}, "scenario_contract", where
    )
    path = directory / contract
    if not path.is_file():
        raise SpecError(f"{path} not found")

    return path, cast(
        "object", yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def _named_contract_scenarios(
    document: object, path: Path
) -> Mapping[str, object]:
    mapping = _require_mapping(document or {}, str(path))
    _check_keys(mapping, ("scenarios",), str(path))
    scenarios = _require_mapping(
        mapping.get("scenarios") or {}, f"{path}.scenarios"
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


def _list_contract_scenarios(
    document: object,
    path: Path,
    run: ScenarioRunSpec,
    directory: Path,
    variant: str | None,
    variant_where: str,
) -> Mapping[str, ScenarioSpec]:
    contract = _require_mapping(document or {}, str(path))
    entries = _require_list(contract.get("scenarios"), f"{path}.scenarios")
    if not entries:
        raise SpecError(f"{path}: declares no scenarios")

    parsed: dict[str, ScenarioSpec] = {}
    selected_variant = False
    for index, value in enumerate(entries):
        where = f"{path}.scenarios[{index}]"
        entry = _require_mapping(value, where)
        _check_keys(entry, ("description", "action", "expect"), where)
        description = _required_string(entry, "description", where)
        action = _parse_action(entry.get("action"), f"{where}.action")
        if "expect" not in entry:
            raise SpecError(f"{where}.expect is required")
        expect = _require_mapping(entry["expect"], f"{where}.expect")
        expectation_where = f"{where}.expect"
        telemetry_keys = set(expect) & set(_SCENARIO_CONTRACT_KEYS)
        variant_keys = set(expect) - set(_SCENARIO_CONTRACT_KEYS)
        if variant is not None and variant in expect:
            expectation_where = f"{expectation_where}.{variant}"
            expect = _require_mapping(expect[variant], expectation_where)
            selected_variant = True
        elif not telemetry_keys and expect:
            if variant is None and all(
                isinstance(candidate, Mapping) for candidate in expect.values()
            ):
                raise SpecError(
                    f"{expectation_where}: scenario_contract_variant is "
                    f"required; available variants: {sorted(expect)}"
                )
            if variant is not None:
                raise SpecError(
                    f"{expectation_where}: unknown scenario contract variant "
                    f"{variant!r}; available variants: {sorted(expect)}"
                )
        elif variant is None and any(
            not isinstance(expect[key], Mapping) for key in variant_keys
        ):
            _check_keys(expect, _SCENARIO_CONTRACT_KEYS, expectation_where)
        else:
            expect = {key: expect[key] for key in telemetry_keys}
        _check_keys(expect, _SCENARIO_CONTRACT_KEYS, expectation_where)
        name = f"{index:04d}"
        parsed[name] = _parse_scenario(
            name,
            expect,
            directory,
            expectation_where,
            description=description,
            index=index,
            action=action,
            run_spec=run,
        )
    if variant is not None and not selected_variant:
        raise SpecError(
            f"{variant_where}: unknown scenario contract variant {variant!r}; "
            "the contract has no variant expectations"
        )
    return parsed


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
            "scenario_contract_variant",
            "scenario_run",
            "instrumented_library",
            "instrumentation_library",
            "env",
            "weaver",
            "server",
            "setup",
            "scenarios",
            "additional_metrics",
            "additional_spans",
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
    expected_violations = tuple(
        _parse_violation(violation, f"{path}.expected_violations[{index}]")
        for index, violation in enumerate(
            _require_list(
                document.get("expected_violations") or [],
                f"{path}.expected_violations",
            )
        )
    )

    contract_document: object | None = None
    contract_path: Path | None = None
    if "scenario_contract" in document:
        contract_path, contract_document = _load_scenario_contract(
            directory,
            document["scenario_contract"],
            str(path),
        )
    contract_scenario_declarations = (
        _require_mapping(
            contract_document if contract_document is not None else {},
            str(contract_path),
        ).get("scenarios")
        if contract_path is not None
        else None
    )
    if isinstance(contract_scenario_declarations, list):
        if local_scenarios:
            raise SpecError(
                f"{path}: scenarios cannot be combined with an indexed "
                "contract; use scenario_run"
            )
        if "scenario_run" not in document:
            raise SpecError(
                f"{path}: scenario_run is required for an indexed contract"
            )
        assert contract_path is not None
        variant = (
            _required_string(document, "scenario_contract_variant", str(path))
            if "scenario_contract_variant" in document
            else None
        )
        parsed_scenarios = _list_contract_scenarios(
            cast("object", contract_document),
            contract_path,
            _parse_scenario_run(
                document["scenario_run"], f"{path}.scenario_run"
            ),
            directory,
            variant,
            f"{path}.scenario_contract_variant",
        )
        contract = _require_mapping(
            cast("object", contract_document), str(contract_path)
        )
        readiness_value = contract.get("readiness")
        if readiness_value is None:
            action_table = ()
        else:
            readiness = _require_mapping(
                readiness_value, f"{contract_path}.readiness"
            )
            _check_keys(
                readiness,
                ("description", "action"),
                f"{contract_path}.readiness",
            )
            _required_string(
                readiness, "description", f"{contract_path}.readiness"
            )
            action_table = (
                _parse_action(
                    readiness.get("action"),
                    f"{contract_path}.readiness.action",
                ),
                *(
                    scenario.action
                    for scenario in parsed_scenarios.values()
                    if scenario.action is not None
                ),
            )
    else:
        action_table = ()
        if "scenario_run" in document:
            raise SpecError(
                f"{path}: scenario_run requires an indexed contract"
            )
        if "scenario_contract_variant" in document:
            raise SpecError(
                f"{path}: scenario_contract_variant requires an indexed "
                "contract"
            )
        named_contract_scenarios: Mapping[str, object] = (
            _named_contract_scenarios(contract_document, contract_path)
            if contract_path is not None
            else {}
        )
        declared = _merge_scenarios(
            named_contract_scenarios, local_scenarios, path
        )
        if not declared:
            raise SpecError(f"{path}: declares no scenarios")
        parsed_scenarios = {
            name: _parse_scenario(
                name,
                scenario,
                directory,
                f"{path}.scenarios.{name}",
            )
            for name, scenario in declared.items()
        }

    additional_metrics, optional_metrics = _parse_additional_metrics(
        document.get("additional_metrics"), f"{path}.additional_metrics"
    )
    additional_spans = tuple(
        _parse_span(span, f"{path}.additional_spans[{index}]")
        for index, span in enumerate(
            _require_list(
                document.get("additional_spans") or [],
                f"{path}.additional_spans",
            )
        )
    )
    if additional_metrics or optional_metrics or additional_spans:
        parsed_scenarios = {
            name: _with_package_additions(
                scenario,
                additional_metrics,
                optional_metrics,
                additional_spans,
            )
            for name, scenario in parsed_scenarios.items()
        }

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
        expected_violations=expected_violations,
        scenarios=parsed_scenarios,
        action_table=action_table,
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
