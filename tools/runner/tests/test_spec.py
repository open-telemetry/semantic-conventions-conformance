# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Parsing ``conformance.yaml``.

A misparse silently weakens a check, so the cases that matter are the ones
where an invalid file must raise rather than be tolerated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from opentelemetry.conformance import (
    ServerSpec,
    SpanMatch,
    SpecError,
    WeaverSpec,
    load_spec,
    scenarios,
)

MINIMAL = """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  inference:
    run: python inference.py
"""


def write(tmp_path: Path, document: str) -> Path:
    (tmp_path / "conformance.yaml").write_text(document)
    return tmp_path


def test_minimal_spec_leaves_every_expectation_unchecked(
    tmp_path: Path,
) -> None:
    spec = load_spec(write(tmp_path, MINIMAL))

    assert spec.instrumented_library == "demo"
    assert spec.instrumentation_library == "demo-instrumentation"
    scenario = spec.scenarios["inference"]
    assert scenario.run == ("python", "inference.py")
    assert scenario.spans is None
    assert scenario.metrics is None
    assert scenario.allowed_metrics == ()
    assert scenario.events is None
    assert scenario.expected_violations == ()


def test_runner_config_is_available_to_the_selected_runner(
    tmp_path: Path,
) -> None:
    spec = load_spec(
        write(
            tmp_path,
            MINIMAL
            + """
runner_config:
  backend: postgresql
""",
        )
    )

    assert spec.runner_config == {"backend": "postgresql"}


def test_runner_config_must_be_a_mapping(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match=r"conformance.yaml.runner_config"):
        load_spec(
            write(
                tmp_path,
                MINIMAL
                + """
runner_config: postgresql
""",
            )
        )


def test_declared_but_empty_is_checked_exactly(tmp_path: Path) -> None:
    spec = load_spec(
        write(
            tmp_path,
            MINIMAL
            + """
    spans: []
    metrics: []
    events: []
""",
        )
    )

    scenario = spec.scenarios["inference"]
    assert scenario.spans == ()
    assert scenario.metrics == ()
    assert scenario.events == ()


def test_allowed_metrics_are_parsed(tmp_path: Path) -> None:
    spec = load_spec(
        write(
            tmp_path,
            MINIMAL
            + """
    metrics:
      - db.client.operation.duration
    allowed_metrics:
      - queueSize
""",
        )
    )

    scenario = spec.scenarios["inference"]
    assert scenario.metrics == ("db.client.operation.duration",)
    assert scenario.allowed_metrics == ("queueSize",)


def test_allowed_metrics_require_metric_expectations(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="metrics must be declared"):
        load_spec(
            write(
                tmp_path,
                MINIMAL
                + """
    allowed_metrics:
      - queueSize
""",
            )
        )


def test_scenarios_keeps_declaration_order(tmp_path: Path) -> None:
    directory = write(
        tmp_path,
        """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  zebra:
    run: python zebra.py
  alpha:
    run: python alpha.py
""",
    )

    assert scenarios(directory) == ["zebra", "alpha"]


def test_scenario_contract_supplies_shared_expectations(
    tmp_path: Path,
) -> None:
    (tmp_path / "client.yaml").write_text(
        """
scenarios:
  client:
    spans:
      - match:
          attributes:
            http.request.method: GET
        expect:
          count: 4
    metrics:
      - http.client.request.duration
    allowed_metrics:
      - otlp.exporter.seen
    events: []
"""
    )
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: client.yaml
scenarios:
  client:
    run: python client.py
""",
        )
    )

    scenario = spec.scenarios["client"]
    assert scenario.run == ("python", "client.py")
    assert scenario.spans is not None
    assert scenario.spans[0].count == 4
    assert scenario.metrics == ("http.client.request.duration",)
    assert scenario.allowed_metrics == ("otlp.exporter.seen",)
    assert scenario.events == ()


def test_local_scenario_replaces_a_contract_expectation(
    tmp_path: Path,
) -> None:
    (tmp_path / "client.yaml").write_text(
        """
scenarios:
  client:
    metrics:
      - http.client.request.duration
"""
    )
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: client.yaml
scenarios:
  client:
    run: python client.py
    metrics: []
""",
        )
    )

    assert spec.scenarios["client"].metrics == ()


@pytest.mark.parametrize(
    ("contract", "message"),
    [
        pytest.param(
            "server: {}\nscenarios: {client: {spans: []}}",
            "unknown key",
            id="unknown-contract-key",
        ),
        pytest.param(
            "scenarios: {client: {run: python client.py}}",
            "unknown key",
            id="contract-command",
        ),
        pytest.param(
            "scenarios: {}",
            "declares no scenarios",
            id="empty-contract",
        ),
    ],
)
def test_invalid_scenario_contract_raises(
    tmp_path: Path, contract: str, message: str
) -> None:
    (tmp_path / "client.yaml").write_text(contract)

    with pytest.raises(SpecError, match=message):
        load_spec(
            write(
                tmp_path,
                """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: client.yaml
scenarios:
  client:
    run: python client.py
""",
            )
        )


def test_missing_scenario_contract_raises(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="missing.yaml not found"):
        load_spec(
            write(
                tmp_path,
                """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: missing.yaml
scenarios:
  client:
    run: python client.py
""",
            )
        )


def test_command_may_be_a_list(tmp_path: Path) -> None:
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  inference:
    run: ["python", "a b.py"]
""",
        )
    )

    assert spec.scenarios["inference"].run == ("python", "a b.py")


def test_span_expectation(tmp_path: Path) -> None:
    spec = load_spec(
        write(
            tmp_path,
            MINIMAL
            + """
    spans:
      - match:
          attributes:
            gen_ai.operation.name: chat
          kind: CLIENT
        expect:
          count: 2
          attributes:
            gen_ai.tool.name: {distinct: 2}
            server.address: {present: true}
            gen_ai.request.model: gpt-4o-mini
""",
        )
    )

    spans = spec.scenarios["inference"].spans
    assert spans is not None
    (expectation,) = spans
    assert expectation.count == 2
    assert expectation.match.kind == "CLIENT"
    assert expectation.match.attributes == {"gen_ai.operation.name": "chat"}
    assert expectation.attributes["gen_ai.tool.name"].distinct == 2
    assert expectation.attributes["server.address"].present is True
    assert expectation.attributes["gen_ai.request.model"].equals == (
        "gpt-4o-mini"
    )


def test_span_keys_survive_separators_in_a_value() -> None:
    """The keys land in a committed data file; two selections can't collide."""
    one = SpanMatch(attributes={"a": "x,b=y"})
    two = SpanMatch(attributes={"a": "x", "b": "y"})

    assert one.key() != two.key()
    assert json.loads(one.key()) == {"a": "x,b=y"}
    # Same facets, same bytes, whatever order they were declared in.
    assert SpanMatch(attributes={"b": "2", "a": "1"}).key() == (
        SpanMatch(attributes={"a": "1", "b": "2"}).key()
    )


@pytest.mark.parametrize(
    ("document", "message"),
    [
        pytest.param("scenarios: {}", "instrumented_library", id="no-library"),
        pytest.param(
            "instrumented_library: demo\nscenarios:\n  a:\n    run: x",
            "instrumentation_library",
            id="no-instrumentation-library",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation",
            "no scenarios",
            id="no-scenarios",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nscenarios:\n  a: {}",
            "run is required",
            id="scenario-without-run",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nnonsense: 1\nscenarios:\n  a:\n    run: x",
            "unknown key",
            id="unknown-top-level-key",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nscenarios:\n  a:\n    run: x\n    span: []",
            "unknown key",
            id="misspelled-scenario-key",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nenv:\n  PORT: 8080\nscenarios:\n  a:\n    run: x",
            "must be strings",
            id="unquoted-env-number",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nscenarios:\n  a:\n    run: x\n"
            "    spans:\n      - expect: {count: 1}",
            "match is required",
            id="span-without-match",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nscenarios:\n  a:\n    run: x\n"
            "    spans:\n      - match:\n          attributes: {}\n"
            "        expect: {count: 1}",
            "at least one thing to match on",
            id="empty-match",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nscenarios:\n  a:\n    run: x\n"
            "    spans:\n      - match:\n          kind: CLIENT\n"
            "        expect: {}",
            "count is required",
            id="span-without-count",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nscenarios:\n  a:\n    run: x\n"
            "    expected_violations:\n      - id: some_advice",
            "reason is required",
            id="violation-without-reason",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nscenarios:\n  a:\n    run: x\n    events: notalist",
            "expected a list",
            id="events-not-a-list",
        ),
        pytest.param(
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\nserver:\n  port: 8080\nscenarios:\n"
            "  a:\n    run: x",
            "unknown key",
            id="unknown-server-key",
        ),
    ],
)
def test_invalid_spec_raises(
    tmp_path: Path, document: str, message: str
) -> None:
    with pytest.raises(SpecError, match=message):
        load_spec(write(tmp_path, document))


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="not found"):
        load_spec(tmp_path)


def test_matcher_wants_exactly_one_form(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="exactly one"):
        load_spec(
            write(
                tmp_path,
                MINIMAL
                + """
    spans:
      - match:
          kind: CLIENT
        expect:
          count: 1
          attributes:
            a: {present: true, distinct: 2}
""",
            )
        )


class TestOver:
    """A package's block falls back to the runner's defaults, field by field."""

    def test_weaver_takes_defaults_per_field(self) -> None:
        merged = WeaverSpec(registry="mine").over(
            WeaverSpec(registry="theirs", policies="theirs", config="theirs")
        )

        assert merged.registry == "mine"
        assert merged.policies == "theirs"
        assert merged.config == "theirs"

    def test_server_without_run_takes_every_default(self) -> None:
        defaults = ServerSpec(run=("serve",), health="/ready", url_var="URL")

        assert ServerSpec().over(defaults) == defaults

    def test_a_package_may_override_only_the_health_path(self) -> None:
        """The runner's server, checked at a different endpoint."""
        merged = ServerSpec(health="/ready").over(ServerSpec(run=("theirs",)))

        assert merged.run == ("theirs",)
        assert merged.health_path == "/ready"
        assert merged.url_variable == "MOCK_SERVER_URL"

    def test_undeclared_fields_fall_back_to_the_built_in_defaults(
        self,
    ) -> None:
        spec = ServerSpec(run=("serve",))

        assert spec.health_path == "/health"
        assert spec.url_variable == "MOCK_SERVER_URL"


def test_server_block_may_declare_only_a_health_path(tmp_path: Path) -> None:
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
server:
  health: /ready
scenarios:
  a:
    run: x
""",
        )
    )

    assert spec.server.run is None
    assert spec.server.health_path == "/ready"


def test_a_violation_context_is_optional_and_distinct_from_an_empty_one(
    tmp_path: Path,
) -> None:
    """Omitted means "any context"; `{}` means "the finding carried none"."""
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  inference:
    run: x
    expected_violations:
      - id: missing_attribute
        reason: the implementation's own namespace
      - id: genai_span_status_ok_set_by_instrumentation
        context: {}
        reason: carries no context
      - id: genai_span_kind_unexpected
        context: {kind: internal}
        reason: known
""",
        )
    )

    bulk, empty, exact = spec.scenarios["inference"].expected_violations
    assert bulk.context is None
    assert empty.context == {}
    assert exact.context == {"kind": "internal"}


PACKAGE_VIOLATIONS = """
instrumented_library: demo
instrumentation_library: demo-instrumentation
expected_violations:
  - id: missing_attribute
    reason: the implementation's own namespace, everywhere
scenarios:
  inference:
    run: x
  tool_calling:
    run: x
    expected_violations:
      - id: genai_span_kind_unexpected
        context: {kind: internal}
        reason: only this one
"""


def test_package_violations_reach_every_scenario(tmp_path: Path) -> None:
    spec = load_spec(write(tmp_path, PACKAGE_VIOLATIONS))

    inference = spec.scenarios["inference"]
    tool_calling = spec.scenarios["tool_calling"]

    assert [v.id for v in spec.expected_violations] == ["missing_attribute"]
    # Inherited stays separate from a scenario's own: only its own are
    # required to still be reported.
    assert [v.id for v in inference.inherited_violations] == [
        "missing_attribute"
    ]
    assert inference.expected_violations == ()
    assert [v.id for v in tool_calling.inherited_violations] == [
        "missing_attribute"
    ]
    assert [v.id for v in tool_calling.expected_violations] == [
        "genai_span_kind_unexpected"
    ]


def test_redeclaring_a_package_violation_in_a_scenario_is_an_error(
    tmp_path: Path,
) -> None:
    """Two reasons for one id, and no way to tell which still applies."""
    document = """
instrumented_library: demo
instrumentation_library: demo-instrumentation
expected_violations:
  - id: missing_attribute
    reason: everywhere
scenarios:
  inference:
    run: x
    expected_violations:
      - id: missing_attribute
        context: {attribute_key: llm.system}
        reason: here too
"""

    with pytest.raises(SpecError, match="already declared"):
        load_spec(write(tmp_path, document))
