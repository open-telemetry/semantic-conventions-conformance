# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared scenario-data generation and normalization helpers."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from semconv_conformance.attribute_spec import AttributeSpec, RequirementLevel
from semconv_conformance.locations import ScenarioLocation, iter_scenario_locations
from semconv_conformance.parse_results import ScenarioResult, merge_signal_counts


@dataclass(frozen=True)
class RequirementLevelInfo:
    key: RequirementLevel
    label: str
    description: str


@dataclass(frozen=True)
class SignalTypeAttributeGroup:
    level: RequirementLevelInfo
    attrs: tuple[str, ...]


class GeneratedScenarioData(NamedTuple):
    path: Path
    data: dict[str, object]
    has_relevant_data: bool


@dataclass(frozen=True)
class ScenarioDataEntry:
    scenario_id: str
    lang: str
    library: str
    ecosystem: str
    library_display: str
    language_display: str
    ecosystem_display: str
    spans: dict[str, dict[str, str]] = field(default_factory=dict)
    metrics: dict[str, dict[str, str]] = field(default_factory=dict)
    events: dict[str, dict[str, str]] = field(default_factory=dict)
    opt_in_env_var: str = ""

    @property
    def label(self) -> str:
        suffix = " *" if self.opt_in_env_var else ""
        return f"{self.library_display} ({self.language_display}) — {self.ecosystem_display}{suffix}"


_REQUIREMENT_LEVELS = (
    RequirementLevel.REQUIRED,
    RequirementLevel.CONDITIONALLY_REQUIRED,
    RequirementLevel.RECOMMENDED,
    RequirementLevel.OPT_IN,
)

_SIGNAL_TYPE_LEVELS = (
    RequirementLevelInfo(RequirementLevel.REQUIRED, "Required", "Must be present for spans of this type."),
    RequirementLevelInfo(
        RequirementLevel.CONDITIONALLY_REQUIRED,
        "Conditionally Required",
        "Required only when the span matches the relevant condition.",
    ),
    RequirementLevelInfo(RequirementLevel.RECOMMENDED, "Recommended", "Expected when the library exposes the signal."),
    RequirementLevelInfo(RequirementLevel.OPT_IN, "Opt-In", "Captured only when the user explicitly enables it."),
)


class DomainDataFiles:
    """Generate and normalize the committed scenario data for one domain."""

    def __init__(
        self,
        *,
        domain_dir: Path,
        language_display_names: dict[str, str],
        language_slugs: dict[str, str],
        ecosystem_display: dict[str, str],
        library_display_name: Callable[[str], str],
        parse_result_dir: Callable[[Path, ScenarioLocation], ScenarioResult | None],
        span_specs: dict[str, AttributeSpec],
        metric_specs: dict[str, AttributeSpec],
        event_specs: dict[str, AttributeSpec],
        span_type_order: list[str],
        deprecated_attr_aliases: dict[str, str] | None = None,
        required_opt_in_env_var: Callable[[str, str, str], str] | None = None,
    ) -> None:
        self.domain_dir = domain_dir
        self.language_display_names = dict(language_display_names)
        self.language_slugs = dict(language_slugs)
        self.ecosystem_display = dict(ecosystem_display)
        self.library_display_name = library_display_name
        self.parse_result_dir = parse_result_dir
        self.span_specs = dict(span_specs)
        self.metric_specs = dict(metric_specs)
        self.event_specs = dict(event_specs)
        self.span_type_order = list(span_type_order)
        self.deprecated_attr_aliases = dict(deprecated_attr_aliases or {})
        self.required_opt_in_env_var = required_opt_in_env_var or (lambda _lang, _library, _ecosystem: "")

    def present_attributes(self, result: ScenarioResult) -> set[str]:
        """Return all attribute names present in registry and non-registry stats."""
        attrs = set(result.observed.attrs)
        attrs.update(result.observed.non_registry_attrs)
        return attrs

    def _display_attrs_for_level(self, spec: AttributeSpec, level: RequirementLevel) -> tuple[str, ...]:
        display_attrs: list[str] = []
        for attr in sorted(spec.attrs_for_requirement_level(level)):
            display_attrs.append(attr)
            deprecated_attr = self.deprecated_attr_aliases.get(attr)
            if deprecated_attr is not None:
                display_attrs.append(deprecated_attr)
        return tuple(display_attrs)

    def _attrs_by_level(self, spec: AttributeSpec) -> list[tuple[RequirementLevel, tuple[str, ...]]]:
        return [
            (level, attrs)
            for level in _REQUIREMENT_LEVELS
            for attrs in [self._display_attrs_for_level(spec, level)]
            if attrs
        ]

    def attr_names(self, spec: AttributeSpec) -> list[str]:
        return [attr for _, attrs in self._attrs_by_level(spec) for attr in attrs]

    def signal_type_attribute_groups(self, spec: AttributeSpec) -> list[SignalTypeAttributeGroup]:
        level_info = {info.key: info for info in _SIGNAL_TYPE_LEVELS}
        return [SignalTypeAttributeGroup(level_info[level], attrs) for level, attrs in self._attrs_by_level(spec)]

    def span_type_present_attributes(
        self,
        result: ScenarioResult,
        span_type_key: str,
        level: RequirementLevel,
    ) -> set[str]:
        all_present = self.present_attributes(result)
        if level is RequirementLevel.REQUIRED:
            return result.spans.per_type_attrs.get(span_type_key, all_present)
        return result.spans.per_type_any_attrs.get(span_type_key, all_present)

    def relevant_span_type_keys(self, result: ScenarioResult) -> list[str]:
        all_present = self.present_attributes(result)
        relevant: list[str] = []
        for span_type_key in self.span_type_order:
            spec = self.span_specs[span_type_key]
            expected_attrs = self.attr_names(spec)
            if not expected_attrs:
                continue
            if spec.discriminator_attrs:
                if span_type_key in result.spans.detected_types:
                    relevant.append(span_type_key)
            elif any(attr in all_present for attr in expected_attrs):
                relevant.append(span_type_key)
        return relevant

    def build_statuses_from_present_names(
        self,
        expected_names: list[str],
        present_names: list[str] | set[str],
    ) -> dict[str, str]:
        present = set(present_names)
        return {name: "present" if name in present else "absent" for name in expected_names}

    def build_span_type_present_names(self, result: ScenarioResult) -> dict[str, list[str]]:
        sparse: dict[str, list[str]] = {}
        for span_type_key in self.relevant_span_type_keys(result):
            spec = self.span_specs[span_type_key]
            present_names: list[str] = []
            for level, attrs in self._attrs_by_level(spec):
                type_present = self.span_type_present_attributes(result, span_type_key, level)
                present_names.extend(attr for attr in attrs if attr in type_present)
            sparse[span_type_key] = present_names
        return sparse

    def event_type_present_attributes(
        self,
        result: ScenarioResult,
        event_name: str,
        level: RequirementLevel,
    ) -> set[str]:
        all_present = self.present_attributes(result)
        if level is RequirementLevel.REQUIRED:
            return result.detected.event_attrs.get(event_name, all_present)
        return result.detected.event_any_attrs.get(event_name, all_present)

    def metric_type_present_attributes(
        self,
        result: ScenarioResult,
        metric_name: str,
        level: RequirementLevel,
    ) -> set[str]:
        all_present = self.present_attributes(result)
        if level is RequirementLevel.REQUIRED:
            return result.detected.metric_attrs.get(metric_name, all_present)
        return result.detected.metric_any_attrs.get(metric_name, all_present)

    def _build_signal_type_present_names(
        self,
        attr_specs: dict[str, AttributeSpec],
        merged_counts: dict[str, int],
        present_fn: Callable[[str, RequirementLevel], set[str]],
    ) -> dict[str, list[str]]:
        sparse: dict[str, list[str]] = {}
        for signal_name, spec in attr_specs.items():
            if merged_counts.get(signal_name, 0) <= 0:
                continue
            present_names: list[str] = []
            for level, attrs in self._attrs_by_level(spec):
                type_present = present_fn(signal_name, level)
                present_names.extend(attr for attr in attrs if attr in type_present)
            sparse[signal_name] = present_names
        return sparse

    def build_event_type_present_names(self, result: ScenarioResult) -> dict[str, list[str]]:
        if not self.event_specs:
            return {}
        merged = merge_signal_counts(result.observed.events, result.detected.events)
        return self._build_signal_type_present_names(
            self.event_specs,
            merged,
            lambda name, level: self.event_type_present_attributes(result, name, level),
        )

    def build_metric_type_present_names(self, result: ScenarioResult) -> dict[str, list[str]]:
        merged = merge_signal_counts(result.observed.metrics, result.detected.metrics)
        return self._build_signal_type_present_names(
            self.metric_specs,
            merged,
            lambda name, level: self.metric_type_present_attributes(result, name, level),
        )

    def entry_kwargs_from_result(self, result: ScenarioResult) -> dict[str, Any]:
        language_display = result.language
        lang_slug = self.language_slugs.get(language_display, language_display.lower())
        return {
            "scenario_id": self.make_anchor_id(language_display, result.library, result.ecosystem),
            "lang": lang_slug,
            "library": result.library,
            "ecosystem": result.ecosystem,
            "library_display": self.library_display_name(result.library),
            "language_display": language_display,
            "ecosystem_display": self.ecosystem_display.get(result.ecosystem, result.ecosystem),
            "spans": {},
            "metrics": {},
            "events": {},
            "opt_in_env_var": self.required_opt_in_env_var(lang_slug, result.library, result.ecosystem),
        }

    def _normalize_generated_scenario_payload(self, data: dict[str, object]) -> dict[str, object]:
        normalized: dict[str, object] = {}
        for key in ("spans", "metrics", "events"):
            value = data.get(key)
            if not isinstance(value, dict):
                continue
            cleaned = {
                signal_name: sorted(attrs) if isinstance(attrs, (list, set, tuple)) else []
                for signal_name, attrs in value.items()
                if attrs
            }
            if cleaned:
                normalized[key] = cleaned
        return normalized

    def _build_single_scenario_data(self, location: ScenarioLocation, result: ScenarioResult) -> GeneratedScenarioData:
        event_present = self.build_event_type_present_names(result)
        metric_present = self.build_metric_type_present_names(result)
        spans = self.build_span_type_present_names(result)
        path = location.data_file(self.domain_dir)

        data: dict[str, object] = {
            "events": event_present,
            "metrics": metric_present,
        }
        if spans:
            data["spans"] = spans

        return GeneratedScenarioData(
            path=path,
            data=self._normalize_generated_scenario_payload(data),
            has_relevant_data=bool(spans) or bool(metric_present) or bool(event_present),
        )

    def generate_single_scenario_data(self, location: ScenarioLocation) -> GeneratedScenarioData | None:
        result_dir = location.results_dir(self.domain_dir)
        result = self.parse_result_dir(result_dir, location)
        if result is None:
            return None
        return self._build_single_scenario_data(location, result)

    def make_anchor_id(self, language: str, library: str, ecosystem: str) -> str:
        lang_slug = self.language_slugs.get(language, language.lower())
        return f"{library}-{lang_slug}-{ecosystem}"

    def _normalize_signal_type_data(
        self,
        value: object,
        attr_specs: dict[str, AttributeSpec],
    ) -> dict[str, dict[str, str]]:
        if not isinstance(value, dict):
            return {}

        normalized: dict[str, dict[str, str]] = {}
        for type_key, spec in attr_specs.items():
            if type_key not in value:
                continue
            expected_names = self.attr_names(spec)
            raw = value[type_key]
            present_names = (
                [name for name in raw if isinstance(name, str)] if isinstance(raw, (dict, list, set, tuple)) else []
            )
            normalized[type_key] = self.build_statuses_from_present_names(expected_names, present_names)
        return normalized

    def _display_value(self, value: object, default: str) -> str:
        return value if isinstance(value, str) else default

    def _normalize_scenario_data_entry(self, entry: dict[str, object], location: ScenarioLocation) -> ScenarioDataEntry:
        language_display = self._display_value(
            entry.get("language"),
            self.language_display_names.get(location.lang, location.lang),
        )
        return ScenarioDataEntry(
            scenario_id=self.make_anchor_id(language_display, location.library, location.ecosystem),
            lang=location.lang,
            library=location.library,
            ecosystem=location.ecosystem,
            library_display=self._display_value(entry.get("library"), self.library_display_name(location.library)),
            language_display=language_display,
            ecosystem_display=self._display_value(
                entry.get("ecosystem"),
                self.ecosystem_display.get(location.ecosystem, location.ecosystem),
            ),
            spans=self._normalize_signal_type_data(entry.get("spans"), self.span_specs),
            metrics=self._normalize_signal_type_data(entry.get("metrics"), self.metric_specs),
            events=self._normalize_signal_type_data(entry.get("events"), self.event_specs),
            opt_in_env_var=self.required_opt_in_env_var(location.lang, location.library, location.ecosystem),
        )

    def entry_from_result(self, result: ScenarioResult) -> ScenarioDataEntry:
        return ScenarioDataEntry(**self.entry_kwargs_from_result(result))

    def load_scenario_data_files(self) -> list[ScenarioDataEntry]:
        entries: list[ScenarioDataEntry] = []
        if not self.domain_dir.is_dir():
            return entries
        for location in iter_scenario_locations(self.domain_dir):
            data_file = location.data_file(self.domain_dir)
            data = json.loads(data_file.read_text(encoding="utf-8"))
            entries.append(self._normalize_scenario_data_entry(data, location))
        return entries
