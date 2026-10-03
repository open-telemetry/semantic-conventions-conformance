# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The environment a scenario process runs with."""

from __future__ import annotations

import logging
import os

import pytest

from opentelemetry.conformance._env import build_env, timeout_seconds


@pytest.fixture(autouse=True)
def process_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """An empty process environment; a test that needs one writes into it."""
    environment: dict[str, str] = {}
    monkeypatch.setattr(os, "environ", environment)
    return environment


def test_scenario_wins_over_package() -> None:
    env = build_env(
        {"KEY": "package", "ONLY_PACKAGE": "a"},
        {"KEY": "scenario"},
        injected={},
    )

    assert env["KEY"] == "scenario"
    assert env["ONLY_PACKAGE"] == "a"


def test_process_environment_wins_over_declared(
    process_env: dict[str, str],
) -> None:
    process_env["OPENAI_API_KEY"] = "real"

    env = build_env({"OPENAI_API_KEY": "placeholder"}, injected={})

    assert env["OPENAI_API_KEY"] == "real"


def test_injected_values_cannot_be_shadowed(
    process_env: dict[str, str],
) -> None:
    """They name the server and collector this run actually started."""
    process_env["OTEL_EXPORTER_OTLP_ENDPOINT"] = "ambient"

    env = build_env(
        {"OTEL_EXPORTER_OTLP_ENDPOINT": "declared"},
        injected={"OTEL_EXPORTER_OTLP_ENDPOINT": "real"},
    )

    assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "real"


def test_declared_values_reference_injected_names() -> None:
    env = build_env(
        {"OPENAI_BASE_URL": "${MOCK_SERVER_URL}/v1"},
        injected={"MOCK_SERVER_URL": "http://127.0.0.1:1234"},
    )

    assert env["OPENAI_BASE_URL"] == "http://127.0.0.1:1234/v1"


def test_unknown_reference_is_left_alone() -> None:
    env = build_env({"A": "${NOPE}"}, injected={})

    assert env["A"] == "${NOPE}"


def test_an_override_is_reported(
    caplog: pytest.LogCaptureFixture, process_env: dict[str, str]
) -> None:
    """A stray export must not look like an instrumentation change."""
    variable = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"
    process_env[variable] = "NO_CONTENT"

    with caplog.at_level(logging.WARNING):
        build_env({variable: "SPAN_ONLY"}, injected={})

    assert variable in caplog.text


def test_nothing_overridden_is_quiet(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        build_env({"A": "1"}, injected={})

    assert caplog.text == ""


@pytest.mark.parametrize(
    "raw", ["nan", "inf", "+Infinity", "-inf", "1e309", "0", "-1", "invalid"]
)
def test_invalid_timeout_uses_default(
    raw: str,
    process_env: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    variable = "OTEL_CONFORMANCE_WEAVER_STOP_TIMEOUT"
    process_env[variable] = raw

    assert timeout_seconds(variable, 120.0) == 120.0
    assert variable in caplog.text
    assert "using 120.0" in caplog.text


@pytest.mark.parametrize("raw", [None, ""])
def test_unset_timeout_uses_default_quietly(
    raw: str | None,
    process_env: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    variable = "OTEL_CONFORMANCE_WEAVER_STOP_TIMEOUT"
    if raw is not None:
        process_env[variable] = raw

    assert timeout_seconds(variable, 120.0) == 120.0
    assert caplog.text == ""


@pytest.mark.parametrize(
    ("raw", "expected"), [("0.25", 0.25), ("600", 600.0), ("1e2", 100.0)]
)
def test_finite_positive_timeout_is_preserved(
    raw: str,
    expected: float,
    process_env: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    variable = "OTEL_CONFORMANCE_SCENARIO_TIMEOUT"
    process_env[variable] = raw

    assert timeout_seconds(variable, 600.0) == expected
    assert caplog.text == ""
