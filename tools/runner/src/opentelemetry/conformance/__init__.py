# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Semantic-convention conformance runner.

A conformance directory holds standalone scenario programs, a
``conformance.yaml`` saying how to run each and what it must produce, and a
committed ``data.json`` of the coverage a run recorded. The runner carries no
semantic conventions of its own: the caller says which registry and policies
to check against. The core is a library owning the server and weaver
lifecycles::

    with conformance_session(conformance_dir) as session:
        report = session.run("inference")

``run`` returns rather than raises whatever the scenario got wrong — a count
mismatch, a crash — in ``report.failures``, and what it emitted that departs
from the conventions in ``report.violations``; only a broken harness raises.
What a finding means is the caller's: pytest asserts on both, the CLI turns
them into an exit code, and calling the library directly records without
failing.
"""

from ._cli import main
from ._coverage import coverage
from ._domain import Domain
from ._model import load as load_coverage_model
from ._model import resolve as resolve_coverage_model
from ._registry import (
    WeaverNotInstalledError,
    cache_dir,
    check_weaver,
    provision,
    require_pin,
)
from ._report import ClassifySpan
from ._runners import domain
from ._semconv import semconv_coverage
from ._session import (
    ConformanceSession,
    ScenarioReport,
    SessionFactory,
    conformance_session,
)
from ._spec import (
    AttributeMatcher,
    ExpectedViolation,
    PackageSpec,
    ScenarioSpec,
    ServerSpec,
    SpanExpectation,
    SpanMatch,
    SpecError,
    WeaverSpec,
    load_spec,
    scenarios,
)

__all__ = [
    "AttributeMatcher",
    "ClassifySpan",
    "ConformanceSession",
    "Domain",
    "WeaverNotInstalledError",
    "check_weaver",
    "coverage",
    "ExpectedViolation",
    "PackageSpec",
    "ScenarioReport",
    "ScenarioSpec",
    "ServerSpec",
    "SessionFactory",
    "SpanExpectation",
    "SpanMatch",
    "SpecError",
    "WeaverSpec",
    "cache_dir",
    "conformance_session",
    "domain",
    "load_coverage_model",
    "load_spec",
    "main",
    "provision",
    "require_pin",
    "resolve_coverage_model",
    "scenarios",
    "semconv_coverage",
]
