# `otel-conformance-report`

Every conformance directory commits a `data.json` recording what its
instrumentation emitted. This tool reads all of them, compares each against the
semantic conventions it was measured against, and writes a report the
[site](../../docs) reads.

Those conventions — the *registry* — are not committed here. Each domain pins
the upstream semantic-conventions repo at a git ref in its own `versions.env`,
and the report asks a domain's package which pin to use, so every domain
package has to be installed alongside this one. From the repo root, once:

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

Each command rebuilds the whole report, so all three need `weaver` on `PATH`
and will fetch every pinned registry the first time.

The rebuild runs nightly in the [`Report`](../../.github/workflows/report.yml)
workflow, which opens a pull request when the report changed. The site updates
when that pull request is merged. Nothing rebuilds on the pull request that
bumps a pin, so a registry or instrumentation bump will show up in the next
nightly run. We can manually dispatch the workflow to see it sooner if needed.

## What the report contains

One entry per *target*: one conformance directory, so one library, one
instrumentation, one language. A target is any `conformance.yaml` with a
`data.json` beside it, in one of these layouts:

```text
scenarios/<domain>/<language>/<library>/<instrumentation>
scenarios/http/<language>/<library>/<instrumentation>/<client|server>
scenarios/database/<language>/<backend>/<library>/<instrumentation>
```

The path supplies the language, the client/server side and the database
backend. The library and instrumentation names come from the `conformance.yaml`
itself, which wins over anything the path suggests. A path matching none of
these layouts results in an error rather than a mislabeled target.

The output types are in [`_types.py`](src/conformance_report/_types.py).
Registry declarations and findings are copied through from the runner
unchanged. `schema_version` changes when the output changes incompatibly, and
the schema is still experimental.

## How to read the numbers

**There is no single conformance score.**

The registry declares each attribute at one of five requirement levels, and an
absent attribute means something different at each one — e.g. an `opt_in` attribute
is not a gap, by definition. Below is a table that outlines how to interpret scores.

| Level | Is an absence a gap? |
| --- | --- |
| `required` | Yes. Scored. |
| `recommended` | Usually. Scored separately, because an instrumentation may have had nothing to put there. |
| `conditionally_required_conditional` | Unknowable from one run — whether the condition held is not in the data. Counted, never scored. |
| `recommended_conditional` | Same. Counted, not scored. |
| `opt_in` | No. Counted, not scored. |

Only the first two count toward a target's coverage (`SCORED_LEVELS` in
[`_aggregate.py`](src/conformance_report/_aggregate.py)). The other three are
reported as per-signal counts, a signal being one span type, metric or event.

An attribute counts as *emitted* when at least one observation carried it with
an accepted type.

Every number has two inputs: what the instrumentation emitted the last time its
scenarios ran and its `data.json` was committed, and what the registry pin
declares now. Either one changing will impact the results. Semconv adding attributes
can lower coverage for an instrumentation that did not change at all, which is expected.
This helps track when conventions grow and the instrumentation have not caught
up. The report and the site footer name the pins each number was computed
against.

## Findings

A finding is one thing weaver flagged: an `id`, a message, the signal it was
reported on, and its context. Weaver's
[finding reference](https://github.com/open-telemetry/weaver/blob/main/crates/weaver_live_check/docs/finding.md)
defines those fields, its three severity levels and every built-in `id`. The
IDs it does not list come from the runner's and each domain's
[advice policies](../runner/README.md#advice-policies).

Only `violation` findings — telemetry weaver reads as breaking the conventions
— reach the data files (`_RECORDED_LEVEL` in
[`_report.py`](../runner/src/opentelemetry/conformance/_report.py)).
`improvement` and `information` are dropped today and may be included later.

Coverage and findings can disagree about one attribute without contradicting
each other: one observation carrying it makes it emitted, while another missing
it is a finding. A value with a `type_mismatch` never counts as emitted, though
a valid value elsewhere still does.
