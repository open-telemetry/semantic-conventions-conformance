# `otel-conformance-report`

Joins every committed `data.json` to what the pinned registry declares, and writes
the report the [site](../../docs) reads.

A `data.json` only holds a numerator: it records which of a signal's declared
attributes a run carried, not how many there were to carry. The denominator comes
from the coverage model — weaver's resolution of the pinned registry, which is
cached rather than committed. This tool joins the two and commits the result, so
the site needs neither weaver nor a registry.

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

`build` is deterministic — sorted keys, sorted sequences, no timestamp. The
committed file is compared byte-for-byte against a rebuild, so a rebuild that only
reordered a list would open a pull request every night saying nothing.

The rebuild runs nightly in the [`Report`](../../.github/workflows/report.yml)
workflow, which opens a pull request when the report changed. It is not a
pull-request gate: resolving the denominator needs weaver and a fetched registry,
and making every scenario change wait on that buys nothing the nightly rebuild
does not. So the committed report, and the site that publishes it, can be a day
behind a merge. Run `check` locally to see whether that is the case.

`markdown --against` renders what changed into that pull request's body: both
halves of every ratio, not only the numerator. Attributes gained and lost, signals
appearing and going, findings, and any registry pin that moved. A moved pin is
listed first, because it explains every changed denominator under it.

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
| `opt_in` | No. Off by default is the correct behaviour. Counted, not scored. |

Only the first two are summed into a target's coverage (`SCORED_LEVELS` in
[`_aggregate.py`](src/conformance_report/_aggregate.py)). The other three are
reported per signal as counts.

Coverage is measured against both an instrumentation version and a semconv
version. If new attributes are added to semconv, e.g., coverage will change for an
instrumentation even though its version did not. That is expected, and is why the
report is regenerated whenever either pin moves. Which registry each domain was
read against is in `conformance.json`, and in the site's footer.

## Findings

A finding is one piece of weaver advice. Weaver grades advice at three levels —
[`violation`, `improvement` and `information`](https://github.com/open-telemetry/weaver/blob/main/crates/weaver_live_check/docs/finding.md#weaverfindinglevel)
— and `violation` means weaver thinks the telemetry breaks semantic conventions.

Today the reduction keeps only `violation`
(`_RECORDED_LEVEL` in
[`_report.py`](../runner/src/opentelemetry/conformance/_report.py)), so every
finding in the report is one, and the id is all that distinguishes them. That is
how it works now, not a decision for all time: recording the other two levels
would give findings something to rank on.

**Most findings are absences, not malformed telemetry.** Weaver records an
attribute the registry requires and the run did not carry as a violation, so most
findings restate a coverage gap rather than describing something the run got
wrong. The two are worth keeping apart when reading a target:

| Finding | What it means |
| --- | --- |
| `missing_attribute`, `required_attribute_not_present`, `recommended_attribute_not_present`, `genai_expected_attribute_missing`, `error_type_missing_on_error`, `missing_event`, `missing_metric` | An absence. The same gap the coverage bars show, counted a second way. |
| `type_mismatch`, `unit_mismatch`, `genai_span_name_format`, `span_status_ok_set_by_instrumentation` | Something arrived, and was wrong. |

One case is both: an attribute that arrives holding a type the registry does not
allow is recorded as a `type_mismatch` **and** left out of coverage, because
counting it would claim conformance the run did not have. So it can be in the
findings list and absent from the emitted list at once.
