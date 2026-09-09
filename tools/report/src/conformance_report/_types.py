# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""JSON output types for the report builder."""

from typing import Any, TypedDict


class Tally(TypedDict):
    emitted: int
    declared: int


class SpanIdentity(TypedDict):
    attributes: list[str]
    span_kind: str | None


class _Signal(TypedDict):
    type: str
    name: str
    emitted: list[str]


class Signal(_Signal, total=False):
    # Unknown declarations omit coverage, missing and identity.
    declared: None
    missing: list[str]
    coverage: dict[str, Tally]
    identity: SpanIdentity


class Summary(TypedDict):
    required: Tally
    recommended: Tally
    findings: int


class ReportTarget(TypedDict):
    id: str
    path: str
    domain: str
    language: str
    side: str | None
    backend: str | None
    runner: str
    instrumented_library: str
    instrumentation_library: str
    label: str
    scenario_classes: list[str]
    signals: list[Signal]
    # These objects pass through from the runner without reinterpretation.
    entities: dict[str, Any]
    findings: list[dict[str, Any]]
    summary: Summary


class RegistryPin(TypedDict):
    registry_repo: str
    registry_ref: str
    registry_dir: str


class Report(TypedDict):
    schema_version: int
    generated_by: str
    domains: dict[str, RegistryPin]
    registry: dict[str, Any]
    targets: list[ReportTarget]
