# `otel-conformance-report`

Joins every `data.json` to what the pinned registry declares, and writes
the report the [site](../../docs) reads.

Every target names a `runner:`, and reading what its registry declares means
importing that runner, so the domain wrappers have to be installed alongside this
package. From the repo root, once:

```sh
python -m pip install \
  -e tools/runner -e tools/database/runner \
  -e tools/gen-ai/runner -e tools/gen-ai/mock-server \
  -e tools/http/runner -e tools/http/mock-server \
  -e tools/http/test-client/python -e tools/report
```

```sh
otel-conformance-report build    # write docs/data/conformance.json
otel-conformance-report check    # fail if a rebuild would differ
otel-conformance-report markdown # summarise for a job summary
```

All three resolve a coverage model, so they need `weaver` on `PATH` and will fetch
each pinned registry the first time.

The rebuild runs nightly in the [`Report`](../../.github/workflows/report.yml)
workflow, which opens a pull request when the report changed.
The site updates when that pull request is merged.

## Report format

The output types are defined in [`_types.py`](src/conformance_report/_types.py).
`schema_version` changes when the output changes incompatibly. Registry
declarations and findings retain the runner's format.

Discovery reads `conformance.yaml` files with an adjacent `data.json` under:

```text
scenarios/<domain>/<language>/<library>/<instrumentation>
scenarios/http/<language>/<library>/<instrumentation>/<client|server>
scenarios/database/<language>/<backend>/<library>/<instrumentation>
```

Library coordinates come from the spec. The path supplies the language,
instrumentation label, and optional side and database backend. Unsupported
layouts fail rather than produce incorrect labels.

## How to read the numbers

**There is no single conformance score.**

We track attributes at five requirement levels. For `opt-in`, e.g., an absence is
*not* a gap in conformance, by definition. Blending all five into one percentage
would produce a number that reads as a grade and is not one.

| Level | Is an absence a gap? |
| --- | --- |
| `required` | Yes. Scored. |
| `recommended` | Usually. Scored separately, because an instrumentation may have had nothing to put there. |
| `conditionally_required_conditional` | Unknowable from one run — whether the condition held is not in the data. Counted, never scored. |
| `recommended_conditional` | Same. Counted, not scored. |
| `opt_in` | No. Counted, not scored. |

Only the first two are summed into a target's coverage (`SCORED_LEVELS` in
[`_aggregate.py`](src/conformance_report/_aggregate.py)). The other three are
reported per signal as counts.

Coverage combines committed observations with the current pinned registry.
Changing the registry can change coverage without changing the instrumentation.
The report and site footer identify the registry pins used for aggregation.

An attribute counts as emitted if it was observed at least once with an accepted
type. Coverage does not show whether every observation conformed, and only
signals that were observed contribute to the totals.

## Findings

A finding is one piece of weaver advice. Weaver grades advice at three levels —
[`violation`, `improvement` and `information`](https://github.com/open-telemetry/weaver/blob/main/crates/weaver_live_check/docs/finding.md#weaverfindinglevel)
— and `violation` means weaver thinks the telemetry breaks semantic conventions.

Today the reduction keeps only `violation`
(`_RECORDED_LEVEL` in
[`_report.py`](../runner/src/opentelemetry/conformance/_report.py)). Findings
retain their IDs, messages, signal names and context. Other severity levels may
be included in future versions.

| Finding | What it means |
| --- | --- |
| `missing_attribute`, `missing_event`, `missing_metric` | An emitted attribute, event or metric is not defined in the registry. |
| `required_attribute_not_present`, `recommended_attribute_not_present`, `genai_expected_attribute_missing`, `error_type_missing_on_error` | An expected attribute was absent from an observation. |
| `type_mismatch`, `unit_mismatch`, `genai_span_name_format`, `span_status_ok_set_by_instrumentation` | An emitted value, unit, name or status violated a convention. |

Findings and coverage are not interchangeable. An attribute can count as emitted
because one observation carried it, while another observation produces a finding
for its absence or invalid type. Values with a `type_mismatch` do not contribute
to coverage; a valid value observed elsewhere still can.
