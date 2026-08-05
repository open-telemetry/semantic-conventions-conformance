# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Per-domain configuration object for the conformance framework.

A :class:`Domain` bundles all the state needed to run scenarios, parse Weaver
output, and regenerate committed ``data-<eco>.json`` files for a single
semantic-conventions domain. Each domain instance lives under its
subpackage's ``__init__`` and is imported by CLI entry points and CI scripts.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

from semconv_conformance.attribute_spec import AttributeSpec
from semconv_conformance.cli import make_run_scenario_entrypoint
from semconv_conformance.data_files import DomainDataFiles
from semconv_conformance.language_adapters import DomainLanguageAdapters, UvNotInstalledError
from semconv_conformance.metadata import ALL_DEPENDENCY_VERSION_READERS, DomainMetadata, MetadataError
from semconv_conformance.parse_results import DomainResultParser, IgnoreAdvice

if TYPE_CHECKING:
    from semconv_conformance.data_files import GeneratedScenarioData
    from semconv_conformance.locations import ScenarioLocation
    from semconv_conformance.parse_results import ScenarioResult
    from semconv_conformance.runner import PipelineHook


@dataclass
class Domain:
    """Configuration and lazily-built services for one conformance domain."""

    name: str
    domain_dir: Path

    language_display_names: dict[str, str]
    supported_languages: Iterable[str]

    span_specs: dict[str, AttributeSpec]
    metric_specs: dict[str, AttributeSpec]
    event_specs: dict[str, AttributeSpec]
    span_type_order: list[str]

    metric_prefix: str
    classify_span: Callable[[str, str, dict[str, object]], set[str]]

    default_otlp_protocol: Callable[[ScenarioLocation], str] = field(default=lambda _location: "grpc")
    event_prefix: str | None = None
    ignore_advice: IgnoreAdvice | None = None
    deprecated_attr_aliases: dict[str, str] = field(default_factory=dict)

    extra_env: dict[str, str] = field(default_factory=dict)
    weaver_health_timeout: int = 30
    inactivity_timeout: int = 60
    hook: PipelineHook | None = None
    extra_error_types: tuple[type[Exception], ...] = (UvNotInstalledError, MetadataError)

    @cached_property
    def metadata(self) -> DomainMetadata:
        return DomainMetadata(
            domain_dir=self.domain_dir,
            language_display_names=self.language_display_names,
            dependency_version_readers={
                language: ALL_DEPENDENCY_VERSION_READERS[language] for language in self.language_display_names
            },
        )

    @cached_property
    def language_adapters(self) -> DomainLanguageAdapters:
        return DomainLanguageAdapters(
            domain_dir=self.domain_dir,
            supported_languages=self.supported_languages,
        )

    @cached_property
    def parser(self) -> DomainResultParser:
        return DomainResultParser(
            domain_dir=self.domain_dir,
            language_display_names=self.language_display_names,
            metric_prefix=self.metric_prefix,
            event_prefix=self.event_prefix,
            classify_span=self.classify_span,
            ignore_advice=self.ignore_advice,
        )

    @cached_property
    def data_files(self) -> DomainDataFiles:
        return DomainDataFiles(
            domain_dir=self.domain_dir,
            language_display_names=self.language_display_names,
            language_slugs=self.metadata.language_slugs,
            ecosystem_display=self.metadata.ecosystem_display,
            library_display_name=self.metadata.library_display_name,
            parse_result_dir=self.parser.parse_result_dir,
            span_specs=self.span_specs,
            metric_specs=self.metric_specs,
            event_specs=self.event_specs,
            span_type_order=self.span_type_order,
            deprecated_attr_aliases=self.deprecated_attr_aliases,
            required_opt_in_env_var=self.metadata.required_opt_in_env_var,
        )

    # ── ``DomainConfig`` protocol surface (consumed by runner.py) ──────
    # Domain satisfies runner.DomainConfig structurally; no wrapper dataclass.

    @property
    def parse_result_dir(self) -> Callable[[Path, ScenarioLocation], ScenarioResult | None]:
        return self.parser.parse_result_dir

    @property
    def generate_single_scenario_data(self) -> Callable[[ScenarioLocation], GeneratedScenarioData | None]:
        return self.data_files.generate_single_scenario_data

    @property
    def required_opt_in_env_var(self) -> Callable[[str, str, str], str]:
        return self.metadata.required_opt_in_env_var

    # ``dashboard_config`` deliberately does not live here. When the dashboard
    # lands it builds its own config from a ``Domain``, so the model doesn't
    # depend on its presentation layer.

    @property
    def run_scenario_main(self) -> Callable[[], int]:
        return make_run_scenario_entrypoint(self)
