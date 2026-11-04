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
  `conformance.yaml` maps from `${MOCK_SERVER_URL}`. Where an SDK has no such
  variable the program reads one and passes it.
- **One instrumentation per environment.** An implementation directory's
  dependencies must hold only its own instrumentation. A neighbour's would put
  someone else's spans in the results.
- Pin every dependency exactly and commit `uv.lock` (`uv lock` in the
  implementation directory). Renovate bumps them.
- Apache-2.0 header on every `.py` and `conformance.yaml`.

### JavaScript

```
scenarios/gen-ai/js/
    package.json, package-lock.json   one npm workspace for every library
    <library>/
        scenarios/          package.json, common.js, <class>.js
        <instrumentation>/  package.json, conformance.yaml, <class>.js,
                            data.json
```

The rules above hold, with these differences:

- **The shared scenarios are a package.** `<library>/scenarios/` is a
  workspace package (`@otel-conformance/<library>-scenarios`) that depends only
  on the client library. Each `<class>.js` exports one async function with the
  exchange, and `common.js` holds the client and request settings the classes
  share.
- **One entry program per class.** JavaScript instrumentation is set up in
  code, so every implementation directory has a `<class>.js` that calls
  `runScenario` from [`tools/js/scenario-sdk`](../../tools/js/scenario-sdk)
  with its instrumentation and requires the matching shared scenario. This is
  the only place OpenTelemetry is named. A library that emits OpenTelemetry
  itself registers its telemetry in a `run.js` beside the entry programs, as
  `vercel-ai/native` does.
- **One instrumentation per package.** An implementation directory's
  `package.json` depends on its library's scenarios package, the scenario SDK
  and its own instrumentation, nothing else.
- Pin every third-party dependency exactly, add a new library to `workspaces`
  in `js/package.json`, and commit the regenerated `js/package-lock.json`
  (`npm install` in `js/`). Run `npm run format` there before committing; CI
  checks formatting.
- Apache-2.0 header on every `.js` and `conformance.yaml`.

## The mock server is where responses come from

A scenario that needs a field the mock does not serve is a change to
[`tools/gen-ai/mock-server`](../../tools/gen-ai/mock-server), meaning a new
branch in the provider's blueprint plus a test. It is never a workaround in
the scenario. The response must stay deterministic: the same request has to
produce the same bytes, because that is what makes a run's coverage
reproducible.

## Before opening a PR

```sh
otel-conformance scenarios/gen-ai/<language>/<library>/<instrumentation> --report-only
```

- Commit the regenerated `data.json`. CI runs every directory and fails on any
  diff, so an out-of-date file is a red build.
- Read the new `data.json` against the registry. An absent attribute has to
  correspond to a real instrumentation gap. If the scenario simply never sent
  the stimulus, fix the scenario.
- Findings are expected and are the point. Do not add `expected_violations`,
  and do not declare span, metric or event expectations. Scenarios here
  measure; they do not assert. A `match` carrying `type` and no `expect`
  beside it is the exception, and only for a span the reduction cannot place:
  it says which type the span is, asserts nothing, and leaves every finding on
  it recorded. Comment why it is there, and drop it once the span identifies
  itself.
