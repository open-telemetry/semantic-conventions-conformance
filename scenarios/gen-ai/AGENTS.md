# Working in `scenarios/gen-ai`

Read [README.md](README.md) first. It holds the scenario contract, and this
file is only the rules for changing the tree.

## Adding a library

```
scenarios/gen-ai/<language>/<library>/
    scenarios/<class>.py     one file per scenario class
    <instrumentation>/       conformance.yaml, pyproject.toml, uv.lock, data.json
```

Name `<instrumentation>` after the instrumentation, dropping the
`instrumentation` and `genai` parts of the distribution name:
`opentelemetry-instrumentation-genai-openai` becomes `opentelemetry-openai`.
When the instrumentation reaches the provider through another package, add it:
the langchain instrumentation over `langchain-openai` is
`opentelemetry-langchain-openai`. A third-party suite is named after the
project — `openinference`, `openllmetry` — and a library that emits
OpenTelemetry itself gets `native`. See
[Third-party and native instrumentations](README.md#third-party-and-native-instrumentations)
for what else changes in those directories.

- **One file per class**, named after the class, covering exactly the exchange
  the README defines for it. Do not merge two classes into one program, and do
  not add a class the README does not list without adding it there first.
- **A program never imports OpenTelemetry** and never names an
  instrumentation. Instrumentation is zero-code, from the packages the
  implementation directory's `pyproject.toml` installs. Instrumentation needing
  programmatic configuration gets an entry program beside `conformance.yaml`,
  importing the shared scenario.
- **A program reads no configuration of its own.** It reaches the mock server
  through the client library's own base-URL environment variable, which
  `conformance.yaml` maps from `${MOCK_SERVER_URL}`.
- **One instrumentation per environment.** An implementation directory's
  dependencies must hold only its own instrumentation. A neighbour's would put
  someone else's spans in the results.
- Pin every dependency exactly and commit `uv.lock` (`uv lock` in the
  implementation directory). Renovate bumps them.
- Apache-2.0 header on every `.py` and `conformance.yaml`.

## The mock server is where responses come from

A scenario that needs a field the mock does not serve is a change to
[`tools/gen-ai/mock-server`](../../tools/gen-ai/mock-server), meaning a new
branch in the provider's blueprint plus a test. It is never a workaround in
the scenario. The response must stay deterministic: the same request has to
produce the same bytes, because that is what makes a run's coverage
reproducible.

## Before opening a PR

```sh
otel-conformance scenarios/gen-ai/python/<library>/<instrumentation> --report-only
```

- Commit the regenerated `data.json`. CI runs every directory and fails on any
  diff, so an out-of-date file is a red build.
- Read the new `data.json` against the registry. An absent attribute has to
  correspond to a real instrumentation gap. If the scenario simply never sent
  the stimulus, fix the scenario.
- Findings are expected and are the point. Do not add `expected_violations`,
  and do not declare span, metric or event expectations. Scenarios here
  measure; they do not assert.
