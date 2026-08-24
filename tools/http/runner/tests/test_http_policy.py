# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""HTTP advice policy behavior."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from http_conformance import DOMAIN
from opentelemetry.conformance import WeaverNotInstalledError, check_weaver

_POLICIES = Path(__file__).parents[1] / "src/http_conformance/policies"
_HTTP_POLICY_IDS = {"http_route_not_present", "http_span_name_format"}


def _server_span(name: str, route: str | None = None) -> dict[str, Any]:
    attributes: dict[str, object] = {
        "http.request.method": "GET",
        "url.path": "/health",
        "url.scheme": "http",
        "client.address": "127.0.0.1",
        "network.protocol.version": "1.1",
        "server.address": "localhost",
    }
    if route is not None:
        attributes["http.route"] = route
    return _span(name, "server", attributes)


def _client_span(name: str, template: str | None = None) -> dict[str, Any]:
    attributes: dict[str, object] = {
        "http.request.method": "GET",
        "network.protocol.version": "1.1",
        "server.address": "example.com",
        "server.port": 443,
        "url.full": "https://example.com/health",
    }
    if template is not None:
        attributes["url.template"] = template
    return _span(name, "client", attributes)


def _span(
    name: str, kind: str, attributes: dict[str, object]
) -> dict[str, Any]:
    return {
        "span": {
            "name": name,
            "kind": kind,
            "attributes": [
                {"name": key, "value": value}
                for key, value in attributes.items()
            ],
        }
    }


@pytest.fixture(scope="module")
def policy_advice(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[tuple[str, str], dict[str, dict[str, Any]]]:
    try:
        check_weaver()
        registry = DOMAIN.registry
    except (WeaverNotInstalledError, OSError, RuntimeError) as error:
        pytest.skip(f"HTTP policy test unavailable: {error}")

    root = tmp_path_factory.mktemp("http-policy")
    input_path = root / "input.json"
    report_dir = root / "report"
    input_path.write_text(
        json.dumps(
            [
                _server_span("GET /health"),
                _server_span(
                    "GET /users/{id}",
                    route="/users/{id}",
                ),
                _server_span("GET"),
                _client_span("HTTP GET"),
                _server_span("POST /wrong-method"),
                _server_span(
                    "GET /users/123",
                    route="/users/{id}",
                ),
                _client_span(
                    "GET /users/123",
                    template="/users/{id}",
                ),
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "weaver",
            "registry",
            "live-check",
            "--quiet",
            "--registry",
            str(registry),
            "--input-source",
            str(input_path),
            "--advice-policies",
            str(_POLICIES),
            "--format",
            "json",
            "--fail-on",
            "none",
            "--no-stream",
            "--output",
            str(report_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    report: dict[str, Any] = json.loads(
        (report_dir / "live_check.json").read_text(encoding="utf-8")
    )
    return {
        (span["kind"], span["name"]): {
            advice["id"]: advice
            for advice in span["live_check_result"]["all_advice"]
            if advice["id"] in _HTTP_POLICY_IDS
        }
        for sample in report["samples"]
        if (span := sample.get("span")) is not None
    }


def test_server_target_without_route_reports_route_evidence_only(
    policy_advice: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> None:
    advice = policy_advice[("server", "GET /health")]

    assert set(advice) == {"http_route_not_present"}
    assert (
        "matched route and target cardinality cannot be verified"
        in advice["http_route_not_present"]["message"]
    )


def test_server_target_matching_route_has_no_finding(
    policy_advice: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> None:
    assert policy_advice[("server", "GET /users/{id}")] == {}


def test_server_method_without_route_has_no_finding(
    policy_advice: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> None:
    assert policy_advice[("server", "GET")] == {}


def test_client_wrong_method_token_reports_span_name(
    policy_advice: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> None:
    assert set(policy_advice[("client", "HTTP GET")]) == {
        "http_span_name_format"
    }


def test_wrong_method_prefix_reports_span_name(
    policy_advice: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> None:
    assert set(policy_advice[("server", "POST /wrong-method")]) == {
        "http_span_name_format"
    }


def test_server_target_mismatch_reports_span_name(
    policy_advice: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> None:
    assert set(policy_advice[("server", "GET /users/123")]) == {
        "http_span_name_format"
    }


def test_client_target_mismatch_reports_span_name(
    policy_advice: dict[tuple[str, str], dict[str, dict[str, Any]]],
) -> None:
    assert set(policy_advice[("client", "GET /users/123")]) == {
        "http_span_name_format"
    }
