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
    ScenarioRunSpec,
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
    assert scenario.events is None


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
    assert scenario.events == ()


def test_scenario_list_contract_generates_one_scenario_per_entry(
    tmp_path: Path,
) -> None:
    (tmp_path / "client.yaml").write_text(
        """
description: Shared HTTP requests.
owner: http
scenarios:
  - description: The same description may repeat.
    action: {request: {method: GET, path: /one}}
    expect:
      spans:
        - match:
            attributes: {url.full: "${SERVER}/one"}
          expect: {count: 1}
  - description: The same description may repeat.
    action: {request: {method: GET, path: /two}}
    expect: {events: []}
"""
    )
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: client.yaml
scenario_run: python client.py
""",
        )
    )

    assert list(spec.scenarios) == ["0000", "0001"]
    first, second = spec.scenarios.values()
    assert first.description == second.description
    assert first.index == 0
    assert second.index == 1
    assert first.action == {"request": {"method": "GET", "path": "/one"}}
    assert second.action == {"request": {"method": "GET", "path": "/two"}}
    assert first.run == second.run == ("python", "client.py")
    assert first.run_spec == ScenarioRunSpec(("python", "client.py"))
    assert first.spans is not None
    assert first.spans[0].match.attributes == {"url.full": "${SERVER}/one"}
    assert second.events == ()


@pytest.mark.parametrize(
    ("contract", "package", "message"),
    [
        ("scenarios: []", "scenario_run: run", "declares no scenarios"),
        ("[]", "scenario_run: run", "expected a mapping"),
        (
            "scenarios:\n  - description: test\n    action: {}\n    expect: {}",
            "scenario_run: run",
            "non-empty mapping",
        ),
        (
            "scenarios:\n  - description: test\n    action: {kind: request}",
            "scenario_run: run",
            "expect is required",
        ),
        (
            "scenarios:\n  - description: test\n    action: {kind: request}\n    expect: {}",
            "",
            "scenario_run is required",
        ),
        (
            "scenarios:\n  - description: test\n    action: {kind: request}\n    expect: {}",
            "scenario_run: run\nscenarios: {local: {run: local}}",
            "cannot be combined",
        ),
        (
            "scenarios:\n  - description: test\n    action: {kind: request}\n    expect: {}",
            'scenario_run: ""',
            "non-empty command",
        ),
        (
            "scenarios:\n  - description: test\n    action: {kind: request}\n    expect: {}",
            "scenario_run: []",
            "non-empty command",
        ),
        (
            "scenarios: {client: {events: []}}",
            "scenario_run: run",
            "requires an indexed contract",
        ),
        (
            "- description: test\n  action: {kind: request}\n  expect: {}",
            "scenario_run: run",
            "expected a mapping",
        ),
        (
            "scenarios:\n  - description: test\n    action: {kind: request}\n    expect: {}\n    id: authored",
            "scenario_run: run",
            "unknown key",
        ),
        (
            "scenarios:\n  - description: test\n    action: {kind: request}\n    expect: {run: local}",
            "scenario_run: run",
            "unknown key",
        ),
        (
            "scenarios:\n  - action: {kind: request}\n    expect: {}",
            "scenario_run: run",
            "description is required",
        ),
        (
            "scenarios:\n  - description: test\n    expect: {}",
            "scenario_run: run",
            "expected a mapping",
        ),
        (
            "scenarios:\n  - description: test\n    action: request\n    expect: {}",
            "scenario_run: run",
            "expected a mapping",
        ),
        (
            "scenarios:\n  - description: test\n    action: {date: 2026-01-01}\n    expect: {}",
            "scenario_run: run",
            "represented as JSON",
        ),
        (
            "scenarios:\n  - description: test\n    action: {nested: {1: value}}\n    expect: {}",
            "scenario_run: run",
            "mapping keys must be strings",
        ),
        (
            "scenarios:\n  - description: test\n    action: {value: .nan}\n    expect: {}",
            "scenario_run: run",
            "represented as JSON",
        ),
        (
            "scenarios:\n  - description: test\n    action: {kind: request}\n    expect: []",
            "scenario_run: run",
            "expected a mapping",
        ),
    ],
)
def test_invalid_scenario_list_contract_raises(
    tmp_path: Path, contract: str, package: str, message: str
) -> None:
    (tmp_path / "client.yaml").write_text(contract)

    with pytest.raises(SpecError, match=message):
        load_spec(
            write(
                tmp_path,
                f"""
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: client.yaml
{package}
""",
            )
        )


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


def test_indexed_contract_keeps_default_expectations_beside_variant(
    tmp_path: Path,
) -> None:
    (tmp_path / "contract.yaml").write_text(
        """
scenarios:
  - description: request
    action: {method: GET}
    expect:
      spans:
        - match: {kind: CLIENT}
          expect: {count: 1}
      server:
        spans:
          - match: {kind: SERVER}
            expect: {count: 1}
"""
    )
    default = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: contract.yaml
scenario_run: run
""",
        )
    )
    server = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: contract.yaml
scenario_contract_variant: server
scenario_run: run
""",
        )
    )

    assert default.scenarios["0000"].spans[0].match.kind == "CLIENT"
    assert server.scenarios["0000"].spans[0].match.kind == "SERVER"


def test_indexed_contract_selects_expectation_variant(tmp_path: Path) -> None:
    (tmp_path / "contract.yaml").write_text(
        """
scenarios:
  - description: request
    action: {method: GET}
    expect:
      client:
        spans:
          - match: {kind: CLIENT}
            expect: {count: 1}
      server: {events: []}
  - description: shared expectation
    action: {method: POST}
    expect: {metrics: []}
"""
    )

    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: contract.yaml
scenario_contract_variant: server
scenario_run: run
""",
        )
    )

    variant_scenario = spec.scenarios["0000"]
    direct_scenario = spec.scenarios["0001"]
    assert variant_scenario.spans is None
    assert variant_scenario.events == ()
    assert direct_scenario.metrics == ()


@pytest.mark.parametrize(
    ("variant", "expectation", "message"),
    [
        (
            "",
            "client: {events: []}\n      server: {events: []}",
            "scenario_contract_variant is required",
        ),
        (
            "proxy",
            "client: {events: []}\n      server: {events: []}",
            "unknown scenario contract variant 'proxy'",
        ),
        (
            "client",
            "client: []",
            r"expect\.client: expected a mapping",
        ),
        (
            "client",
            "client: {run: local}",
            r"expect\.client: unknown key",
        ),
        (
            "client",
            "{}",
            "contract has no variant expectations",
        ),
    ],
)
def test_invalid_contract_variant_raises(
    tmp_path: Path, variant: str, expectation: str, message: str
) -> None:
    (tmp_path / "contract.yaml").write_text(
        f"""
scenarios:
  - description: request
    action: {{method: GET}}
    expect:
      {expectation}
"""
    )
    selected = f"scenario_contract_variant: {variant}\n" if variant else ""

    with pytest.raises(SpecError, match=message):
        load_spec(
            write(
                tmp_path,
                f"""
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: contract.yaml
{selected}scenario_run: run
""",
            )
        )


def test_http_persistent_representatives_share_server_contract() -> None:
    root = Path(__file__).resolve().parents[3]
    packages = {
        root
        / "scenarios/http/python/wsgi/opentelemetry-wsgi/server": (
            "http.server.active_requests",
            "http.server.request.duration",
        ),
        root
        / "scenarios/http/java/java-http-server/opentelemetry-javaagent/server": (
            "http.server.request.duration",
        ),
    }

    for package, metrics in packages.items():
        spec = load_spec(package)
        assert tuple(spec.scenarios) == tuple(
            f"{index:04d}" for index in range(5)
        )
        for scenario in spec.scenarios.values():
            assert scenario.protocol == "jsonl-v1"
            assert scenario.spans is not None
            assert len(scenario.spans) == 1
            assert scenario.spans[0].match.kind == "SERVER"
            assert scenario.spans[0].count == 1
            assert scenario.metrics == metrics

    client = load_spec(
        root
        / "scenarios/http/python/requests/opentelemetry-requests/client"
    )
    assert all(
        scenario.spans is not None
        and scenario.spans[0].match.kind == "CLIENT"
        and scenario.protocol is None
        for scenario in client.scenarios.values()
    )


def test_additional_metrics_extend_only_declared_metric_checks(
    tmp_path: Path,
) -> None:
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
additional_metrics:
  - demo.extra
scenarios:
  measured:
    run: echo measured
    metrics:
      - demo.requests
  unchecked:
    run: echo unchecked
""",
        )
    )

    assert spec.scenarios["measured"].metrics == (
        "demo.extra",
        "demo.requests",
    )
    assert spec.scenarios["unchecked"].metrics is None


def test_optional_metrics_and_additional_spans_permit_without_requiring(
    tmp_path: Path,
) -> None:
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
additional_metrics:
  - demo.extra
  - name: demo.sometimes
    required: false
additional_spans:
  - match:
      kind: INTERNAL
scenarios:
  measured:
    run: echo measured
    metrics:
      - demo.requests
    spans:
      - match:
          kind: SERVER
        expect:
          count: 1
  unchecked:
    run: echo unchecked
""",
        )
    )

    measured = spec.scenarios["measured"]
    assert measured.metrics == ("demo.extra", "demo.requests")
    assert measured.optional_metrics == ("demo.sometimes",)
    assert [
        (expectation.match.kind, expectation.count)
        for expectation in measured.spans or ()
    ] == [("SERVER", 1), ("INTERNAL", None)]
    unchecked = spec.scenarios["unchecked"]
    assert unchecked.metrics is None
    assert unchecked.optional_metrics == ()
    assert unchecked.spans is None


def test_an_optional_metric_needs_a_boolean(tmp_path: Path) -> None:
    with pytest.raises(SpecError, match="required: expected a boolean"):
        load_spec(
            write(
                tmp_path,
                """
instrumented_library: demo
instrumentation_library: demo-instrumentation
additional_metrics:
  - name: demo.sometimes
    required: "no"
scenarios:
  measured:
    run: echo measured
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


def test_scenario_run_protocol_is_explicit_in_the_model(
    tmp_path: Path,
) -> None:
    (tmp_path / "contract.yaml").write_text(
        """
scenarios:
  - description: request
    action: {method: GET}
    expect: {}
"""
    )
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: contract.yaml
scenario_run:
  command: [python, controller.py]
  protocol: jsonl-v1
""",
        )
    )

    scenario = spec.scenarios["0000"]
    assert scenario.run == ("python", "controller.py")
    assert scenario.run_spec == ScenarioRunSpec(
        ("python", "controller.py"), protocol="jsonl-v1"
    )
    assert scenario.run_spec.one_shot is False


@pytest.mark.parametrize(
    ("run", "message"),
    [
        (
            "{command: run, protocol: jsonl-v2}",
            "unknown protocol 'jsonl-v2'",
        ),
        ("{command: run}", "protocol is required"),
        ("{protocol: jsonl-v1}", "command is required"),
        (
            "{command: run, protocol: jsonl-v1, extra: true}",
            "unknown key",
        ),
    ],
)
def test_invalid_scenario_run_mapping_raises(
    tmp_path: Path, run: str, message: str
) -> None:
    (tmp_path / "contract.yaml").write_text(
        """
scenarios:
  - description: request
    action: {method: GET}
    expect: {}
"""
    )

    with pytest.raises(SpecError, match=message):
        load_spec(
            write(
                tmp_path,
                f"""
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenario_contract: contract.yaml
scenario_run: {run}
""",
            )
        )


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
            "instrumented_library: demo\ninstrumentation_library: demo-instrumentation\n"
            "expected_violations:\n  - id: some_advice\nscenarios:\n  a:\n    run: x",
            "reason is required",
            id="package-violation-without-reason",
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


def test_package_violation_context_is_optional_and_distinct_from_an_empty_one(
    tmp_path: Path,
) -> None:
    """Omitted means "any context"; `{}` means "the finding carried none"."""
    spec = load_spec(
        write(
            tmp_path,
            """
instrumented_library: demo
instrumentation_library: demo-instrumentation
expected_violations:
  - id: missing_attribute
    reason: the implementation's own namespace
  - id: genai_span_status_ok_set_by_instrumentation
    context: {}
    reason: carries no context
  - id: genai_span_kind_unexpected
    context: {kind: internal}
    reason: known
scenarios:
  inference:
    run: x
""",
        )
    )

    bulk, empty, exact = spec.expected_violations
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
"""


def test_package_violations_stay_at_package_level(tmp_path: Path) -> None:
    spec = load_spec(write(tmp_path, PACKAGE_VIOLATIONS))

    assert [v.id for v in spec.expected_violations] == ["missing_attribute"]


def test_scenario_expected_violations_is_an_unknown_key(
    tmp_path: Path,
) -> None:
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

    with pytest.raises(SpecError, match="unknown key"):
        load_spec(write(tmp_path, document))
