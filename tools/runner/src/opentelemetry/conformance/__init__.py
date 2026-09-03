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
        scenarios = session.run_all()
        package = session.finalize()

``run_all`` returns process failures per scenario. ``finalize`` returns the
package's aggregate live-check report and findings. Only a broken runner raises.
What a finding means is the caller's: pytest asserts on it, the CLI turns it
into an exit code, and calling the library directly records without failing.
"""

from ._cli import main
from ._coverage import coverage
from ._domain import Domain
from ._model import load as load_coverage_model
from ._model import resolve as resolve_coverage_model
from ._otlp_capture import CapturedSpan, CapturedWindow
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
    PackageReport,
    ScenarioReport,
    SessionFactory,
    conformance_session,
)
from ._spec import (
    AttributeMatcher,
    ExpectedViolation,
    PackageSpec,
    ScenarioRunSpec,
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
    "CapturedSpan",
    "CapturedWindow",
    "Domain",
    "WeaverNotInstalledError",
    "check_weaver",
    "coverage",
    "ExpectedViolation",
    "PackageSpec",
    "PackageReport",
    "ScenarioReport",
    "ScenarioRunSpec",
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
