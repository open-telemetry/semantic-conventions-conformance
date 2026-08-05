# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared result parsing helpers for conformance domains."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from semconv_conformance.locations import ScenarioLocation

logger = logging.getLogger(__name__)


@dataclass
class SpanClassification:
    detected_types: set[str] = field(default_factory=set)
    per_type_attrs: dict[str, set[str]] = field(default_factory=dict)
    per_type_any_attrs: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class DetectedSignals:
    events: dict[str, int] = field(default_factory=dict)
    metrics: dict[str, int] = field(default_factory=dict)
    event_attrs: dict[str, set[str]] = field(default_factory=dict)
    event_any_attrs: dict[str, set[str]] = field(default_factory=dict)
    metric_attrs: dict[str, set[str]] = field(default_factory=dict)
    metric_any_attrs: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class ObservedTelemetry:
    attrs: dict[str, int] = field(default_factory=dict)
    non_registry_attrs: dict[str, int] = field(default_factory=dict)
    metrics: dict[str, int] = field(default_factory=dict)
    events: dict[str, int] = field(default_factory=dict)
    entity_counts: dict[str, int] = field(default_factory=dict)
    has_data: bool = False


@dataclass
class ScenarioResult:
    language: str
    library: str
    ecosystem: str
    statistics: dict | None
    violation_count: int
    violation_messages: list[str]
    observed: ObservedTelemetry = field(default_factory=ObservedTelemetry)
    spans: SpanClassification = field(default_factory=SpanClassification)
    detected: DetectedSignals = field(default_factory=DetectedSignals)

    @property
    def has_detail_content(self) -> bool:
        """Return whether this result contains any renderable detail content."""
        return (
            self.statistics is not None
            or self.observed.has_data
            or bool(self.violation_messages)
            or bool(self.observed.attrs)
            or bool(self.observed.non_registry_attrs)
            or bool(self.spans.detected_types)
            or bool(self.detected.metrics)
            or bool(self.observed.events)
            or bool(self.detected.events)
        )


ClassifySpan = Callable[[str, str, dict[str, object]], set[str]]
IgnoreAdvice = Callable[[ScenarioLocation, dict[str, object], dict[str, object]], bool]


def try_parse_json(content: str, source: Path | str | None = None) -> list[dict]:
    """Parse JSON content, handling a single object, array, or JSONL."""
    objects: list[dict] = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, list):
        objects.extend(data)
        return objects
    if isinstance(data, dict):
        objects.append(data)
        return objects

    location = f" in {source}" if source else ""
    for line_no, raw_line in enumerate(content.strip().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"malformed JSON on line {line_no}{location}: {e.msg}") from e

    return objects


def merge_signal_counts(
    statistics_counts: dict[str, int],
    detected_counts: dict[str, int],
) -> dict[str, int]:
    """Merge statistic-derived and sample-derived signal counts."""
    merged = dict(statistics_counts)
    for name, count in detected_counts.items():
        merged[name] = max(merged.get(name, 0), count)
    return merged


def _non_zero_counts(statistics: dict | None, key: str) -> dict[str, int]:
    if not statistics:
        return {}
    return {name: count for name, count in statistics.get(key, {}).items() if count > 0}


def _extract_statistics(all_objects: list[dict]) -> dict | None:
    statistics = None
    for obj in all_objects:
        if not isinstance(obj, dict):
            continue
        if "statistics" in obj and isinstance(obj["statistics"], dict):
            statistics = obj["statistics"]
            continue
        if "registry_coverage" in obj or "advice_level_counts" in obj:
            statistics = obj
    return statistics


def _supplement_detected_from_statistics(
    detected_counts: dict[str, int],
    statistics: dict | None,
    statistics_key: str,
    signal_prefix: str,
) -> dict[str, int]:
    """Supplement sample-derived signal counts with statistics-only observations."""
    merged = dict(detected_counts)
    if not statistics:
        return merged

    for signal_name, count in statistics.get(statistics_key, {}).items():
        if count <= 0 or not signal_name.startswith(signal_prefix):
            continue
        if count > merged.get(signal_name, 0):
            merged[signal_name] = count
    return merged


class DomainResultParser:
    """Reusable result parser configured with domain-specific hooks."""

    def __init__(
        self,
        *,
        domain_dir: Path,
        language_display_names: dict[str, str],
        metric_prefix: str,
        classify_span: ClassifySpan,
        event_prefix: str | None = None,
        ignore_advice: IgnoreAdvice | None = None,
    ) -> None:
        self.domain_dir = domain_dir
        self.language_display_names = dict(language_display_names)
        self.metric_prefix = metric_prefix
        self.classify_span = classify_span
        self.event_prefix = event_prefix
        self.ignore_advice = ignore_advice

    def _span_attributes(
        self,
        span: dict[str, object],
        include_attr: Callable[[dict[str, object]], bool] | None = None,
    ) -> dict[str, object]:
        attrs: dict[str, object] = {}
        raw_attrs = span.get("attributes", [])
        if not isinstance(raw_attrs, list):
            return attrs
        for attr in raw_attrs:
            if not isinstance(attr, dict):
                continue
            if include_attr is not None and not include_attr(attr):
                continue
            attrs[attr.get("name", "")] = attr.get("value")
        return attrs

    def _span_attribute_names(
        self,
        span: dict[str, object],
        include_attr: Callable[[dict[str, object]], bool] | None = None,
    ) -> set[str]:
        names: set[str] = set()
        raw_attrs = span.get("attributes", [])
        if not isinstance(raw_attrs, list):
            return names
        for attr in raw_attrs:
            if not isinstance(attr, dict):
                continue
            name = attr.get("name")
            if not isinstance(name, str) or not name:
                continue
            if include_attr is not None and not include_attr(attr):
                continue
            names.add(name)
        return names

    def _metric_attribute_names(
        self,
        metric: dict[str, object],
        include_attr: Callable[[dict[str, object]], bool] | None = None,
    ) -> set[str]:
        names: set[str] = set()
        raw_points = metric.get("data_points", [])
        if not isinstance(raw_points, list):
            return names
        for data_point in raw_points:
            if not isinstance(data_point, dict):
                continue
            raw_attrs = data_point.get("attributes", [])
            if not isinstance(raw_attrs, list):
                continue
            for attr in raw_attrs:
                if not isinstance(attr, dict):
                    continue
                name = attr.get("name")
                if not isinstance(name, str) or not name:
                    continue
                if include_attr is not None and not include_attr(attr):
                    continue
                names.add(name)
        return names

    def summarize_samples(
        self,
        all_objects: list[dict],
        include_attr: Callable[[dict[str, object]], bool] | None = None,
    ) -> tuple[SpanClassification, DetectedSignals]:
        """Scan sample payloads once and collect detected spans, events, and metrics."""
        spans = SpanClassification()
        signals = DetectedSignals()
        for obj in all_objects:
            if not isinstance(obj, dict):
                continue
            for sample in obj.get("samples", []):
                span = sample.get("span")
                if isinstance(span, dict):
                    attrs = self._span_attributes(span, include_attr)
                    classified = self.classify_span(
                        str(span.get("name", "")),
                        str(span.get("kind", "")),
                        attrs,
                    )
                    spans.detected_types.update(classified)
                    attr_names = self._span_attribute_names(span, include_attr)
                    for span_type in classified:
                        if span_type not in spans.per_type_attrs:
                            spans.per_type_attrs[span_type] = set(attr_names)
                        else:
                            spans.per_type_attrs[span_type].intersection_update(attr_names)
                        spans.per_type_any_attrs.setdefault(span_type, set()).update(attr_names)

                log = sample.get("log")
                if isinstance(log, dict) and self.event_prefix is not None:
                    event_name = str(log.get("event_name", ""))
                    if event_name.startswith(self.event_prefix):
                        signals.events[event_name] = signals.events.get(event_name, 0) + 1
                        attr_names = self._span_attribute_names(log, include_attr)
                        if event_name not in signals.event_attrs:
                            signals.event_attrs[event_name] = set(attr_names)
                        else:
                            signals.event_attrs[event_name].intersection_update(attr_names)
                        signals.event_any_attrs.setdefault(event_name, set()).update(attr_names)

                metric = sample.get("metric")
                if isinstance(metric, dict):
                    metric_name = str(metric.get("name", ""))
                    if metric_name.startswith(self.metric_prefix):
                        signals.metrics[metric_name] = signals.metrics.get(metric_name, 0) + 1
                        attr_names = self._metric_attribute_names(metric, include_attr)
                        if metric_name not in signals.metric_attrs:
                            signals.metric_attrs[metric_name] = set(attr_names)
                        else:
                            signals.metric_attrs[metric_name].intersection_update(attr_names)
                        signals.metric_any_attrs.setdefault(metric_name, set()).update(attr_names)

        return spans, signals

    def _load_result_objects(self, result_dir: Path) -> list[dict]:
        """Load and parse all JSON result objects from a Weaver result directory."""
        all_objects: list[dict] = []
        for json_file in sorted(result_dir.glob("**/*.json")):
            all_objects.extend(try_parse_json(json_file.read_text(encoding="utf-8"), json_file))
        return all_objects

    def _iter_attribute_advice(self, attribute: dict[str, object]) -> Iterable[dict[str, object]]:
        live_check_result = attribute.get("live_check_result")
        if not isinstance(live_check_result, dict):
            return

        for advice in live_check_result.get("all_advice", []):
            if isinstance(advice, dict):
                yield advice

    def _attribute_blocks_presence(
        self,
        attribute: dict[str, object],
        location: ScenarioLocation,
    ) -> bool:
        for advice in self._iter_attribute_advice(attribute):
            if advice.get("id") == "not_stable":
                continue
            if self.ignore_advice is not None and self.ignore_advice(location, attribute, advice):
                continue
            if advice.get("id") == "type_mismatch":
                return True
        return False

    def _attribute_counts_as_present(
        self,
        attribute: dict[str, object],
        location: ScenarioLocation,
    ) -> bool:
        return not self._attribute_blocks_presence(attribute, location)

    def _iter_attribute_records(self, node: object) -> Iterable[dict[str, object]]:
        """Walk a nested Weaver sample payload, yielding each ``{..., "attributes": [...]}`` entry.

        Weaver's live-check sample output is a recursive tree of dicts and
        lists where some nodes carry an ``attributes`` list (one dict per
        attribute). We descend into every dict/list child and yield each
        attribute dict we encounter.
        """
        if isinstance(node, dict):
            attrs = node.get("attributes")
            if isinstance(attrs, list):
                for attr in attrs:
                    if isinstance(attr, dict):
                        yield attr
            for value in node.values():
                if isinstance(value, (dict, list)):
                    yield from self._iter_attribute_records(value)
            return

        if isinstance(node, list):
            for value in node:
                if isinstance(value, (dict, list)):
                    yield from self._iter_attribute_records(value)

    def _observed_registry_attribute_counts_from_samples(
        self,
        all_objects: list[dict],
        location: ScenarioLocation,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for obj in all_objects:
            if not isinstance(obj, dict):
                continue
            for sample in obj.get("samples", []):
                for attr in self._iter_attribute_records(sample):
                    name = attr.get("name")
                    if not isinstance(name, str) or not name:
                        continue
                    if not self._attribute_counts_as_present(attr, location):
                        continue
                    counts[name] = counts.get(name, 0) + 1
        return counts

    def _observed_telemetry_from_statistics(
        self,
        statistics: dict | None,
        all_objects: list[dict],
        location: ScenarioLocation,
    ) -> ObservedTelemetry:
        """Build observed telemetry counts from Weaver summary statistics."""
        seen_events: dict[str, int] = {}
        if self.event_prefix is not None:
            seen_events = _non_zero_counts(statistics, "seen_registry_events")
            seen_events.update(_non_zero_counts(statistics, "seen_non_registry_events"))

        seen_metrics = _non_zero_counts(statistics, "seen_registry_metrics")
        seen_metrics.update(_non_zero_counts(statistics, "seen_non_registry_metrics"))

        seen_registry_attrs = _non_zero_counts(statistics, "seen_registry_attributes")
        sample_registry_attrs = self._observed_registry_attribute_counts_from_samples(all_objects, location)
        if sample_registry_attrs:
            if seen_registry_attrs:
                seen_registry_attrs = {
                    name: sample_registry_attrs.get(name, 0)
                    for name in seen_registry_attrs
                    if sample_registry_attrs.get(name, 0) > 0
                }
            else:
                seen_registry_attrs = {name: count for name, count in sample_registry_attrs.items() if count > 0}

        entity_counts: dict[str, int] = {}
        has_data = False
        if statistics:
            entity_counts = statistics.get("total_entities_by_type", {})
            has_data = statistics.get("total_entities", 0) > 0

        return ObservedTelemetry(
            attrs=seen_registry_attrs,
            non_registry_attrs=_non_zero_counts(statistics, "seen_non_registry_attributes"),
            metrics=seen_metrics,
            events=seen_events,
            entity_counts=entity_counts,
            has_data=has_data,
        )

    def _detected_signals_from_samples(
        self,
        all_objects: list[dict],
        statistics: dict | None,
        location: ScenarioLocation,
    ) -> tuple[SpanClassification, DetectedSignals]:
        """Classify spans and supplement detected signal counts from statistics."""
        span_classification, detected = self.summarize_samples(
            all_objects,
            include_attr=lambda attr: self._attribute_counts_as_present(attr, location),
        )
        detected.metrics = _supplement_detected_from_statistics(
            detected.metrics,
            statistics,
            "seen_non_registry_metrics",
            self.metric_prefix,
        )
        return span_classification, detected

    def _validate_scenario_lang(self, location: ScenarioLocation) -> None:
        """Raise ValueError if the test location uses an unknown language."""
        if location.lang not in self.language_display_names:
            raise ValueError(f"Invalid scenario id: {location.scenario_id}")

    def _violation_count(self, statistics: dict | None) -> int:
        if not statistics:
            return 0
        return statistics.get("advice_level_counts", {}).get("violation", 0)

    def _violation_messages(self, statistics: dict | None) -> list[str]:
        if not statistics:
            return []

        messages: set[str] = set()
        for message in statistics.get("advice_message_counts", {}):
            if "not stable" in message.lower():
                continue
            messages.add(message)
        return sorted(messages)

    def _build_test_result(
        self,
        location: ScenarioLocation,
        statistics: dict | None,
        observed: ObservedTelemetry,
        spans: SpanClassification,
        detected: DetectedSignals,
    ) -> ScenarioResult:
        """Assemble the final parsed scenario result model."""
        self._validate_scenario_lang(location)
        language = self.language_display_names[location.lang]
        return ScenarioResult(
            language=language,
            library=location.library,
            ecosystem=location.ecosystem,
            statistics=statistics,
            violation_count=self._violation_count(statistics),
            violation_messages=self._violation_messages(statistics),
            observed=observed,
            spans=spans,
            detected=detected,
        )

    def parse_result_dir(self, result_dir: Path, location: ScenarioLocation) -> ScenarioResult | None:
        """Parse a single scenario's Weaver output directory into a ScenarioResult."""
        if not result_dir.is_dir():
            return None

        all_objects = self._load_result_objects(result_dir)
        statistics = _extract_statistics(all_objects)
        observed = self._observed_telemetry_from_statistics(statistics, all_objects, location)
        span_classification, detected = self._detected_signals_from_samples(all_objects, statistics, location)
        return self._build_test_result(
            location,
            statistics,
            observed,
            span_classification,
            detected,
        )

    def parse_all_results(self) -> dict[str, ScenarioResult]:
        """Parse all Weaver output directories under the domain root."""
        results: dict[str, ScenarioResult] = {}

        if not self.domain_dir.exists():
            logger.warning("Scenarios directory not found: %s", self.domain_dir)
            return results

        result_dirs = [path for path in self.domain_dir.glob("*/*/results/*") if path.is_dir()]

        for result_dir in sorted(result_dirs):
            location = ScenarioLocation.from_results_dir(result_dir, self.domain_dir)
            if location.lang not in self.language_display_names:
                logger.warning(
                    "Skipping unsupported result directory: %s",
                    location.scenario_id,
                )
                continue
            result = self.parse_result_dir(result_dir, location)
            if result is None or not result.has_detail_content:
                continue
            results[location.scenario_id] = result

        return results
