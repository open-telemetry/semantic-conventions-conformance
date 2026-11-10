# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Contract semantics use the real session, checks and data reduction."""

from __future__ import annotations

import copy
import json
import sys
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
import yaml

from opentelemetry.conformance import load_spec
from opentelemetry.conformance._checks import check
from opentelemetry.conformance._cli import main
from opentelemetry.conformance._coverage import coverage
from opentelemetry.conformance._semconv import semconv_coverage
from opentelemetry.conformance._session import ConformanceSession
from opentelemetry.conformance._spec import (
    AttributeMatcher,
    ExpectedViolation,
    SpanMatch,
    SpecError,
    WeaverSpec,
)
from opentelemetry.test.weaver_live_check import LiveCheckReport

LPUSH_MATCH = {"attributes": {"db.operation.name": "LPUSH"}, "kind": "CLIENT"}


def package(tmp_path: Path, *, exit_code: int = 0) -> Path:
    (tmp_path / "conformance.yaml").write_text(
        f"""
instrumented_library: redis
instrumentation_library: test
scenarios:
  error:
    run: [{json.dumps(sys.executable)}, '-c', 'raise SystemExit({exit_code})']
    spans:
      - match:
          kind: CLIENT
          attributes: {{db.operation.name: LPUSH}}
        expect:
          count: 1
          attributes: {{error.type: {{present: true}}}}
          semantic_conventions:
            db.response.status_code: WRONGTYPE
"""
    )
    return tmp_path


def report(attributes: dict[str, object]) -> LiveCheckReport:
    return LiveCheckReport(
        {
            "statistics": {},
            "samples": [
                {
                    "span": {
                        "name": "LPUSH",
                        "kind": "CLIENT",
                        "attributes": [
                            {"name": key, "value": value}
                            for key, value in {
                                "db.operation.name": "LPUSH",
                                "error.type": "RedisError",
                                **attributes,
                            }.items()
                        ],
                    }
                }
            ],
        }
    )


@pytest.mark.parametrize("report_only", [False, True])
@pytest.mark.parametrize("exit_code", [0, 7])
@pytest.mark.parametrize("accepted", [False, True])
@pytest.mark.parametrize(
    ("attribute", "attributes", "has_finding"),
    [
        ("db.response.status_code", {}, True),
        (
            "db.response.status_code",
            {"db.response.status_code": "OTHER"},
            True,
        ),
        ("db.response.status_code", {"db.response.status_code": 2}, True),
        (
            "db.response.status_code",
            {"db.response.status_code": "WRONGTYPE"},
            False,
        ),
        ("db.namespace", {}, False),
        ("db.namespace", {"db.namespace": "FREE"}, False),
        ("db.namespace", {"db.namespace": "freepdb1"}, True),
        ("db.namespace", {"db.namespace": 1}, True),
    ],
)
def test_semantic_findings_persist_and_control_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    attributes: dict[str, object],
    has_finding: bool,
    report_only: bool,
    exit_code: int,
    accepted: bool,
) -> None:
    directory = package(tmp_path, exit_code=exit_code)
    if attribute == "db.namespace":
        path = directory / "conformance.yaml"
        path.write_text(
            path.read_text().replace(
                "db.response.status_code: WRONGTYPE",
                "db.namespace: {if_present: FREE}",
            )
        )
    if accepted:
        path = directory / "conformance.yaml"
        path.write_text(
            path.read_text()
            + f"""
    expected_violations:
      - id: contract_attribute_mismatch
        context:
          attribute_key: {attribute}
          scenario: error
          match:
            kind: CLIENT
            attributes: {{db.operation.name: LPUSH}}
        reason: Known omission.
"""
        )
    observed = report(attributes)

    class Weaver:
        def __init__(self, **_kwargs: Any) -> None:
            self.otlp_endpoint = "http://127.0.0.1:1"

        def start(self) -> Weaver:
            return self

        def close(self) -> None:
            pass

        def end(self, **_kwargs: Any) -> LiveCheckReport:
            return observed

    monkeypatch.setattr(
        "opentelemetry.conformance._weaver.WeaverLiveCheck", Weaver
    )

    @contextmanager
    def session(
        _directory: Any, **_kwargs: Any
    ) -> Iterator[ConformanceSession]:
        with ConformanceSession(
            load_spec(directory),
            directory / "reports",
            variables={},
            weaver=WeaverSpec(registry=str(directory)),
            env={},
            data_file=directory / "data.json",
            build_data=coverage,
        ) as opened:
            yield opened

    args = [str(directory), *(["--report-only"] if report_only else [])]
    assert main(args, session=session) == int(
        bool(exit_code) or ((has_finding != accepted) and not report_only)
    )
    data = json.loads((directory / "data.json").read_text())
    assert bool(data["findings"]) is has_finding
    if has_finding:
        finding = data["findings"][0]
        assert finding["id"] == "contract_attribute_mismatch"
        assert finding["context"] == {
            "attribute_key": attribute,
            "scenario": "error",
            "match": LPUSH_MATCH,
        }
        assert finding["signal_name"] == "LPUSH"
        assert finding["signal_type"] == "span"
        assert attribute in finding["message"]
    build = semconv_coverage(lambda *_: {"db.redis.client"}, lambda: {})
    assert (
        build(directory / "reports", load_spec(directory))["findings"]
        == data["findings"]
    )


@pytest.mark.parametrize(
    "semantic",
    [
        None,
        [],
        "WRONGTYPE",
        {"code": {"present": "yes"}},
        {"code": {"typo": True}},
    ],
)
def test_invalid_semantic_contract_is_rejected(
    tmp_path: Path, semantic: object
) -> None:
    directory = package(tmp_path)
    path = directory / "conformance.yaml"
    document = yaml.safe_load(path.read_text())
    document["scenarios"]["error"]["spans"][0]["expect"][
        "semantic_conventions"
    ] = semantic
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(SpecError):
        load_spec(directory)
    assert main([str(directory), "--report-only"]) == 1


def test_semantic_check_does_not_weaken_workload_assertions(
    tmp_path: Path,
) -> None:
    spec = load_spec(package(tmp_path)).scenarios["error"]
    missing = LiveCheckReport({"statistics": {}, "samples": []})
    assert check(spec, missing).failures
    observed = report({})
    observed["samples"][0]["span"]["attributes"] = [
        {"name": "db.operation.name", "value": "LPUSH"}
    ]
    findings = check(spec, observed)
    assert any("error.type" in failure for failure in findings.failures)
    assert any(
        "db.response.status_code" in finding for finding in findings.violations
    )


def test_expected_semantic_findings_still_persist_and_expire(
    tmp_path: Path,
) -> None:
    spec = load_spec(package(tmp_path)).scenarios["error"]
    expected = ExpectedViolation(
        id="contract_attribute_mismatch",
        context={
            "attribute_key": "db.response.status_code",
            "scenario": "error",
            "match": LPUSH_MATCH,
        },
        reason="known instrumentation omission",
    )
    spec = replace(spec, expected_violations=(expected,))
    findings = check(spec, report({}))
    assert not findings.failures
    assert not findings.violations
    assert len(findings.contract_checks) == 1
    fixed = report({"db.response.status_code": "WRONGTYPE"})
    assert "no longer reported" in check(spec, fixed).violations[0]
    inherited = replace(
        spec, expected_violations=(), inherited_violations=(expected,)
    )
    assert not check(inherited, fixed).violations
    other = replace(
        expected, context={"attribute_key": "other", "scenario": "error"}
    )
    assert check(
        replace(spec, expected_violations=(other,)), report({})
    ).violations


@pytest.mark.parametrize("value", [True, 1.0, "1", [1]])
def test_semantic_equality_preserves_attribute_types(
    tmp_path: Path, value: object
) -> None:
    spec = load_spec(package(tmp_path)).scenarios["error"]
    expectation = replace(
        spec.spans[0],
        semantic_conventions={
            "db.operation.batch.size": AttributeMatcher(equals=1)
        },
    )
    spec = replace(spec, spans=(expectation,))
    assert check(spec, report({"db.operation.batch.size": value})).violations
    assert not check(spec, report({"db.operation.batch.size": 1})).violations


def test_a_weaver_rejected_value_cannot_satisfy_a_semantic_check(
    tmp_path: Path,
) -> None:
    spec = load_spec(package(tmp_path)).scenarios["error"]
    observed = report({"db.response.status_code": "WRONGTYPE"})
    observed["samples"][0]["span"]["attributes"][-1]["live_check_result"] = {
        "all_advice": [
            {
                "id": "type_mismatch",
                "level": "violation",
                "message": "invalid value",
            }
        ]
    }
    findings = check(spec, observed)
    assert any(
        "contract_attribute_mismatch" in finding
        and "'WRONGTYPE' (rejected by Weaver)" in finding
        for finding in findings.violations
    )
    assert any("type_mismatch" in finding for finding in findings.violations)


def test_raw_report_survives_a_check_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = package(tmp_path)
    observed = LiveCheckReport({"samples": []})

    @contextmanager
    def weaver(_factory: Any) -> Iterator[SimpleNamespace]:
        yield SimpleNamespace(
            otlp_endpoint="http://127.0.0.1:1", end=lambda **_kwargs: observed
        )

    monkeypatch.setattr(
        "opentelemetry.conformance._session._start_weaver", weaver
    )
    with ConformanceSession(
        load_spec(directory),
        directory / "reports",
        variables={},
        weaver=WeaverSpec(registry=str(directory)),
        env={},
        data_file=directory / "data.json",
        build_data=coverage,
    ) as opened:
        with pytest.raises(KeyError, match="statistics"):
            opened.run("error")
    assert json.loads((directory / "reports/error.json").read_text()) == {
        "samples": []
    }
    assert not (directory / "data.json").exists()


def test_spans_with_the_same_name_and_failure_are_one_finding(
    tmp_path: Path,
) -> None:
    directory = package(tmp_path)
    config = directory / "conformance.yaml"
    config.write_text(config.read_text().replace("count: 1", "count: 2"))
    sample = report({})["samples"][0]
    observed = LiveCheckReport({"statistics": {}, "samples": [sample, sample]})
    findings = check(load_spec(directory).scenarios["error"], observed)
    assert not findings.failures
    assert len(findings.contract_checks) == 1
    assert len(findings.violations) == 1


@pytest.mark.parametrize(
    ("attributes", "violates"),
    [
        ({}, False),
        ({"db.namespace": "FREE"}, False),
        ({"db.namespace": "freepdb1"}, True),
        ({"db.namespace": 1}, True),
    ],
)
def test_semantic_value_can_be_optional(
    tmp_path: Path, attributes: dict[str, object], violates: bool
) -> None:
    directory = package(tmp_path)
    path = directory / "conformance.yaml"
    path.write_text(
        path.read_text().replace(
            "db.response.status_code: WRONGTYPE",
            "db.namespace: {if_present: FREE}",
        )
    )
    spec = load_spec(directory).scenarios["error"]
    findings = check(spec, report(attributes))
    assert not findings.failures
    assert bool(findings.violations) is violates


def test_optional_attribute_rejected_by_weaver_is_still_a_finding(
    tmp_path: Path,
) -> None:
    directory = package(tmp_path)
    path = directory / "conformance.yaml"
    path.write_text(
        path.read_text().replace(
            "db.response.status_code: WRONGTYPE",
            "db.namespace: {if_present: FREE}",
        )
    )
    observed = report({"db.namespace": 1})
    observed["samples"][0]["span"]["attributes"][-1]["live_check_result"] = {
        "all_advice": [
            {
                "id": "type_mismatch",
                "level": "violation",
                "message": "Expected string",
            }
        ]
    }
    findings = check(load_spec(directory).scenarios["error"], observed)
    assert len(findings.contract_checks) == 1
    assert findings.contract_checks[0]["message"] == (
        "db.namespace expected 'FREE' on every span, saw "
        "[1 (rejected by Weaver)]"
    )
    assert findings.contract_checks[0]["context"] == {
        "attribute_key": "db.namespace",
        "scenario": "error",
        "match": LPUSH_MATCH,
    }


def test_accepted_gap_is_specific_to_its_span_selector(tmp_path: Path) -> None:
    spec = load_spec(package(tmp_path)).scenarios["error"]
    lpush = spec.spans[0]
    get = replace(
        lpush,
        match=SpanMatch(
            attributes={"db.operation.name": "GET"}, kind="CLIENT"
        ),
    )
    accepted = ExpectedViolation(
        id="contract_attribute_mismatch",
        context={
            "attribute_key": "db.response.status_code",
            "scenario": "error",
            "match": {
                "attributes": {"db.operation.name": "LPUSH"},
                "kind": "CLIENT",
            },
        },
        reason="LPUSH instrumentation omission",
    )
    spec = replace(spec, spans=(lpush, get), expected_violations=(accepted,))
    observed = report({})
    get_sample = report({})["samples"][0]
    get_sample["span"]["name"] = "GET"
    get_sample["span"]["attributes"][0]["value"] = "GET"
    observed["samples"].append(get_sample)
    findings = check(spec, observed)
    assert not findings.failures
    assert len(findings.violations) == 1
    assert len(findings.contract_checks) == 2
    assert findings.contract_checks[1]["context"]["match"] == {
        "attributes": {"db.operation.name": "GET"},
        "kind": "CLIENT",
    }

    observed["samples"][0]["span"]["attributes"].append(
        {
            "name": "db.response.status_code",
            "value": "WRONGTYPE",
        }
    )
    fixed = check(spec, observed)
    assert not fixed.failures
    assert len(fixed.contract_checks) == 1
    assert len(fixed.violations) == 2
    assert any("no longer reported" in finding for finding in fixed.violations)


def test_saved_finding_names_are_stable_across_mapped_ports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshots = []
    for port in (32802, 32775):
        directory = tmp_path / str(port)
        directory.mkdir()
        package(directory)
        config = directory / "conformance.yaml"
        config.write_text(config.read_text().replace("count: 1", "count: 2"))
        samples = []
        for operation in ("LPUSH", "LPUSH retry"):
            span = report(
                {"server.address": "127.0.0.1", "server.port": port}
            )["samples"][0]["span"]
            span["name"] = f"{operation} 127.0.0.1:{port}"
            # Weaver names the span its own advice is about.
            span["live_check_result"] = {
                "all_advice": [
                    {
                        "id": "missing_attribute",
                        "level": "violation",
                        "message": "Attribute is required",
                        "context": {"attribute_name": "db.query.text"},
                        "signal_type": "span",
                        "signal_name": span["name"],
                    }
                ]
            }
            samples.append({"span": span})
        emitted = copy.deepcopy(samples)
        observed = LiveCheckReport({"statistics": {}, "samples": samples})

        class Weaver:
            def __init__(self, **_kwargs: Any) -> None:
                self.otlp_endpoint = "http://127.0.0.1:1"

            def start(self) -> Weaver:
                return self

            def close(self) -> None:
                pass

            def end(self, **_kwargs: Any) -> LiveCheckReport:
                return observed

        monkeypatch.setattr(
            "opentelemetry.conformance._weaver.WeaverLiveCheck", Weaver
        )
        with ConformanceSession(
            load_spec(directory),
            directory / "reports",
            variables={
                "DATABASE_HOST": "127.0.0.1",
                "DATABASE_PORT": str(port),
            },
            weaver=WeaverSpec(registry=str(directory)),
            env={},
            data_file=directory / "data.json",
            build_data=semconv_coverage(
                lambda *_: {"db.redis.client"}, lambda: {}
            ),
        ) as session:
            result = session.run("error")
            assert not result.failures
        snapshots.append((directory / "data.json").read_bytes())
        saved_report = json.loads(
            (directory / "reports/error.json").read_text()
        )
        assert [s["span"]["name"] for s in saved_report["samples"]] == [
            s["span"]["name"] for s in emitted
        ]
        assert observed["samples"] == emitted
    assert snapshots[0] == snapshots[1]
    findings = json.loads(snapshots[0])["findings"]
    names = {
        "LPUSH 127.0.0.1:${DATABASE_PORT}",
        "LPUSH retry 127.0.0.1:${DATABASE_PORT}",
    }
    contract = [
        finding
        for finding in findings
        if finding["id"] == "contract_attribute_mismatch"
    ]
    weaver = [
        finding for finding in findings if finding["id"] == "missing_attribute"
    ]
    assert {finding["signal_name"] for finding in contract} == names
    assert {finding["signal_name"] for finding in weaver} == names
    assert len(findings) == 4
    assert all(
        finding["context"]["match"] == LPUSH_MATCH for finding in contract
    )


@pytest.mark.parametrize(
    ("name", "host", "port", "expected"),
    [
        (
            "LPUSH 127.0.0.1:32802",
            "127.0.0.1",
            32802,
            "LPUSH 127.0.0.1:${DATABASE_PORT}",
        ),
        (
            "LPUSH 32802 records 127.0.0.1:32802",
            "127.0.0.1",
            32802,
            "LPUSH 32802 records 127.0.0.1:${DATABASE_PORT}",
        ),
        (
            "LPUSH 127.0.0.1:328020",
            "127.0.0.1",
            32802,
            "LPUSH 127.0.0.1:328020",
        ),
        (
            "LPUSH other-host:32802",
            "127.0.0.1",
            32802,
            "LPUSH other-host:32802",
        ),
        ("LPUSH 127.0.0.1:32802", "127.0.0.1", 9999, "LPUSH 127.0.0.1:32802"),
        (
            "LPUSH 127.0.0.1:32802",
            "other-host",
            32802,
            "LPUSH 127.0.0.1:32802",
        ),
        ("LPUSH 32802", "127.0.0.1", 32802, "LPUSH 32802"),
    ],
)
def test_only_the_confirmed_runtime_endpoint_port_changes(
    tmp_path: Path, name: str, host: str, port: int, expected: str
) -> None:
    spec = load_spec(package(tmp_path)).scenarios["error"]
    observed = report({"server.address": host, "server.port": port})
    observed["samples"][0]["span"]["name"] = name
    variables = {"DATABASE_HOST": "127.0.0.1", "DATABASE_PORT": "32802"}
    findings = check(spec, observed, variables=variables)
    assert findings.contract_checks[0]["signal_name"] == expected
    assert check(spec, observed).contract_checks[0]["signal_name"] == name
    assert observed["samples"][0]["span"]["name"] == name
