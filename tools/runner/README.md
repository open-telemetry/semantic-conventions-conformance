# opentelemetry-conformance

Runs scenario programs, collects what they emit through
[Weaver live-check](https://github.com/open-telemetry/weaver), and checks it
against expectations declared in YAML. It carries no semantic conventions of
its own — you tell it which registry and policies to validate against.

Not on PyPI yet — install it from a checkout: `pip install -e tools/runner`.
A Python scenario also wants [`tools/python`](../python), the launcher its
`run` command names.

A *wrapper* supplies those for one set of conventions;
[`gen-ai/runner`](../gen-ai/runner) is one. A directory names the wrapper it
wants and everything else follows from that.

## A conformance directory

A scenario is a plain program — exercise the library, end — sitting next to a
`conformance.yaml` that says how to run each one and what it must produce. No
providers, no test framework, and usually nothing about telemetry at all: it
runs in its own process under whatever agent the `run` command names.

```python
# inference.py
from openai import OpenAI

OpenAI().chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say this is a test"}],
)
```

That the scenario says nothing about instrumentation is what lets the same
program run against several implementations of it.

Which implementation *this* directory is, then, is the one thing the programs
can't say. Three keys say it:

```yaml
# which conventions to check against, by the name of the wrapper that knows
runner: genai-conformance
# what the scenarios exercise
instrumented_library: openai
# what is under test
instrumentation_library: opentelemetry-instrumentation-genai-openai
```

All three are declared rather than read off the directory layout: the runner
never reads a path for meaning, so a directory is a slug, and a data file that
travels out of its checkout still says what produced it. `runner:` is optional
— leave it out to run against a registry passed on the command line; see
[wrapping it](#wrapping-it-for-your-repo).

**Write one scenario per thing you want to know about** — one operation, one
code path. A scenario that exercises everything can only tell you that
*something* is wrong; ten small ones tell you which one.

## Running the scenarios

Every scenario names the command that runs it. The runner tells it where to
export through the environment — OTLP endpoint, protocol, metric interval — so
anything that reads standard OpenTelemetry configuration works. For Python
that is `opentelemetry-instrument`, the zero-code agent:

```yaml
scenarios:
  inference:
    run: opentelemetry-instrument python inference.py
  checkout:
    run: node --require @opentelemetry/auto-instrumentations-node/register checkout.js
```

Zero-code loads every instrumentation it finds installed, so a scenario's
environment should hold only the one under test — otherwise spans nobody
declared show up and fail the run. That is a feature: it's also how one
library gets compared across implementations, by changing only what's
installed.

Which means the run command should build that environment rather than assume
it. In Python, `uv run --project .` syncs a `.venv` beside the directory's
`pyproject.toml` and runs inside it:

```yaml
run: uv run --project . opentelemetry-instrument python inference.py
```

The runner uses OTLP/gRPC unless the package selects OTLP/HTTP protobuf:

```yaml
otlp_protocol: http/protobuf
```

The only accepted values are `grpc` and `http/protobuf`. For HTTP, the runner
starts a local bridge to Weaver and sets `OTEL_EXPORTER_OTLP_ENDPOINT` plus
`OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`, `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`,
and `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`. The signal-specific values include
their `/v1/traces`, `/v1/metrics`, and `/v1/logs` paths. Existing gRPC packages
keep the generic endpoint and `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`.
The bridge is temporary while
[Weaver does not accept OTLP/HTTP directly](https://github.com/open-telemetry/weaver/issues/1563).

Installing into whatever environment happened to be active instead — the
runner's own, say — puts every implementation in one environment, which is
exactly the case above.

A directory can also declare one `setup` command, run once before any
scenario:

```yaml
setup: ./build-fixtures.sh
```

`setup` gets no OTLP endpoint, so whatever it emits stays invisible to the
checks. Use it for building something the scenarios need, or prep API calls —
creating an assistant, seeding a store — that shouldn't count toward any
scenario's expectations. A non-zero exit stops the session. Dependencies
belong in the run command's own environment, per above, not here.

## Driving a run

From the command line:

```sh
otel-conformance path/to/directory --registry …/model --policies …/policies
otel-conformance path/to/directory --scenario inference   # just this one
```

Each scenario prints one line — green `✔`, yellow `▲` for a violation under
`--report-only`, red `✖` — with the findings under it. Colour follows
`NO_COLOR`/`FORCE_COLOR` and is off when stdout isn't a terminal.

Or as a library, when you want the results rather than an exit code:

```python
with conformance_session(directory) as session:
    report = session.run("inference")
    print(report.failures)
```

Anything the scenario got wrong — a mismatch, a crash, a command that won't
start or overruns — lands in `report.failures` rather than raising, and what
it emitted that departs from the conventions lands in `report.violations`,
kept apart because callers weigh the two differently. The weaver report is
written out before anything is checked. (Problems with the harness itself
still raise: an unknown scenario name, a registry that won't load, a missing
`weaver` binary.) Deciding what a finding means is the caller's job, which is
what makes two things easy:

- **Collecting data without failing.** Run everything and report semconv
  violations as warnings — `--report-only`. Useful for measuring attribute
  coverage across a whole repo, or for checking implementations you don't own.
  It only softens `report.violations`; a scenario that crashed, missed a
  declared span or broke `--data-command` still exits 1, because then there is
  nothing to measure.
- **Bringing up a new scenario.** Declare it with no expectations, run it,
  read the dumped report, and write the expectations from what you see.

A run writes two things, configured independently: one raw weaver report per
scenario under `--report-dir`, and one reduction over the whole run to
`--data-file` (`data.json` in the directory by default, and committed).

A scenario's report is replaced each time that scenario runs, and left alone
otherwise — so running one scenario doesn't discard what the others last
reported. The default path sits inside the conformance directory, so sibling
implementations, which run the same scenario names, don't collide — and so a
run lands in the same place however it was invoked:

```
<conformance directory>/output/weaver-reports/<scenario>.json
```

The reduction is the coverage this package computes — for each span a scenario
declares, the attributes it actually carried, plus the metrics and events
seen, plus what weaver said about them:

```json
{
  "spans": [
    {
      "match": {"attributes": {"gen_ai.operation.name": "chat"}},
      "attributes": ["gen_ai.input.messages", "…"]
    }
  ],
  "metrics": ["gen_ai.client.operation.duration"],
  "events": [],
  "findings": [
    {
      "id": "genai_expected_attribute_missing",
      "message": "Span 'chat gpt-4o-mini' … is missing expected attribute 'server.address'",
      "signal_type": "span",
      "signal_name": "chat gpt-4o-mini",
      "context": {"missing_attribute": "server.address", "operation": "chat"}
    }
  ]
}
```

Each span entry pairs a `match` — written the way the scenario declared it —
with the attributes the spans it selected carried.

`findings` is every
violation weaver reported over it, deduplicated on id, message, context and
the signal it was reported on. Weaver's lesser advice — `improvement`,
`information` — is left out: it says what could be better, not what an
implementation got wrong. `signal_type` and `signal_name` say which signal
weaver was looking at — `span`, `metric` or `log`, an event being a log record
— including when the advice was about one of its attributes; a field weaver
reported nothing for is left out, as it is for advice about the resource. The same
gap on the same signal a hundred times is one entry — how often a run tripped
over it says more about the traffic than about the implementation — while the
same gap on two signals is two, because an implementation can fix one and
leave the other.

Diff it to notice an attribute quietly disappearing. `--data-command` replaces
it when you want a different shape.

## Expectations

Expectations are optional — declare them when you want the run to be strict
about what a scenario produces, which is what turns it from a smoke test into
a check:

```yaml
instrumented_library: openai
instrumentation_library: opentelemetry-instrumentation-genai-openai

env:
  OPENAI_BASE_URL: ${MOCK_SERVER_URL}/v1
  OPENAI_API_KEY: test_openai_api_key

scenarios:
  inference:
    run: opentelemetry-instrument python inference.py
    spans:
      - match:
          attributes:
            gen_ai.operation.name: chat
        expect:
          count: 1
    metrics:
      - gen_ai.client.operation.duration
    events: []

  tool_calling:
    run: opentelemetry-instrument python tool_calling.py
    spans:
      - match:
          attributes:
            gen_ai.operation.name: chat
        expect:
          count: 2
      - match:
          attributes:
            gen_ai.operation.name: execute_tool
        expect:
          count: 2
          attributes:
            gen_ai.tool.name:
              distinct: 2
```

Each entry has two halves, declared separately so an attribute used to *find*
a span never reads like one being *checked* on it. `match` selects — by
attribute value or span `kind`. `expect` then asserts over what it selected:
`count` is exact, and a span no entry selects fails as undeclared. Each entry
under `expect.attributes` takes one of three forms:

| form | holds when |
| --- | --- |
| `gen_ai.request.stream: true` | every selected span carries the attribute, set to that value |
| `present: true` | every selected span carries it, whatever the value (`false`: none does) |
| `distinct: 2` | across the selected spans the attribute took exactly 2 different values |

So `gen_ai.tool.name: { distinct: 2 }` above says the two `execute_tool` spans
called two *different* tools, without pinning down which.

`spans`, `metrics` and `events` follow the same rule. A key you leave out is
**not checked** — a scenario with no expectations only has to run cleanly. A
key you write is checked exactly: nothing missing, nothing extra, including
when empty — `events: []` means "emits no events".

`env` configures the scenario process. The real process environment wins over
it, so exporting a real key and base URL points a scenario at a real provider
instead of a mock. What the runner injects — the OTLP endpoint, the server URL
— wins over both, since those name what this run actually started.

### Known violations

Violations weaver reports are failures unless you declare them, with a reason:

```yaml
  tool_calling:
    expected_violations:
      - id: genai_expected_attribute_missing
        context:
          operation: execute_tool
          missing_attribute: gen_ai.tool.call.id
        reason: >-
          The SDK does not expose the tool call id — https://github.com/…/86
```

A declared violation weaver *stops* reporting fails too, so suppressions don't
outlive the gap that caused them.

`context` is matched in full — the same finding `id` with a different context
is a different finding. Leave it out to accept **every** finding with that
`id`, which is what you want when they're one gap seen many times:

```yaml
    expected_violations:
      - id: missing_attribute
        reason: This implementation's own attribute namespace.
```

That trades away some of the signal: a declaration covering a whole class
stops telling you when the class *shrinks*, only when it empties. Reach for it
when the members are interchangeable, and write them out when each is its own
gap. (`context: {}` is not the same thing — it declares a finding that carried
no context at all.)

Declare them at the top level instead, and every scenario gets them — the
right place for a gap that belongs to the instrumentation rather than to one
program:

```yaml
expected_violations:
  - id: genai_span_kind_unexpected
    context: {operation: chat, kind: internal}
    reason: Inference is a remote call, so semconv expects kind=client.
```

A scenario's own list is merged on top. The two levels differ in one way
besides scope: a top-level entry only ever *suppresses*, so a scenario that
doesn't reach that gap isn't failed for it, while a scenario's own is still
required to be reported. Declaring the same `id` at both levels is an error —
two reasons for one finding, and no way to tell which one is stale.

## Advice policies

Weaver checks what a run emits against the registry. On top of that it runs
advice policies — rego files that state what the registry can't. The runner
ships the ones that hold for every domain, in
[`policies/`](src/opentelemetry/conformance/policies): an instrumentation must
not set span status to `OK`, and `error.type` must be set on a failed span and
only on a failed span.

A domain adds its own; the two sets are loaded together. Every file lands in
one rego package, so prefix your helpers.

## The coverage model

A complete run reduces to one committed `data.json`. The built-in reduction
keys it on the spans a scenario *declares*, which is all the runner can do on
its own. A wrapper replaces that with the registry's own view: what each
registry span type, metric and event declares, and which of those attributes
the run carried.

That view is `weaver registry generate --v2` over the
[coverage-model template](src/opentelemetry/conformance/weaver-templates/coverage-model),
resolved once into the cache, under the pin it came from and the template that
produced it. Starting a session resolves it if the pin hasn't got one, so the weaver run
happens up front rather than after the scenarios have. To see what it
resolved, list the cached models and choose the file whose name contains the
pin and fingerprint you need:

```console
python -c "from opentelemetry.conformance import cache_dir; print(*sorted((cache_dir() / 'coverage-models').glob('*.json')), sep='\n')"
```

An attribute counts as covered when any sample of that signal carried it,
whatever its requirement level. A required attribute the implementation
sometimes omits is a semconv violation, which weaver reports and the run fails
on; the signal sections say what an implementation emits, and the `findings`
section beside them says what was wrong with it.

## Wrapping it for your repo

Your repo's conventions — the canonical registry and policies, what a run
should produce — belong in one place, so each directory's YAML stays small.

The lasting way is a wrapper package. It registers a `SessionFactory` under
the `opentelemetry_conformance_runners` entry-point group:

```toml
[project.entry-points.opentelemetry_conformance_runners]
genai-conformance = "genai_conformance:genai_session"
```

and a directory asks for it by that name:

```yaml
runner: genai-conformance
```

`otel-conformance <dir>` and `pytest <dir>` both resolve it, so several
conventions domains coexist in one checkout — each directory gets its own
registry and reduction. A factory is `conformance_session` with defaults
applied; [`genai_conformance/__init__.py`](../gen-ai/runner/src/genai_conformance/__init__.py)
is a whole one. A directory naming no runner runs against whatever the command
line passes.

Everything a wrapper supplies can also be passed on the command line, which is
how you try one out before writing it:

```sh
otel-conformance path/to/directory \
    --registry …/model --policies …/policies \
    --env MOCK_LLM_URL='${MOCK_SERVER_URL}' \
    --server 'env PYTHONPATH=…/src python -m my_mocks.server --port ${PORT}' \
    --data-command ./reduce-coverage
```

`--server` is told its port through `${PORT}` and its base URL reaches the
scenarios as `${MOCK_SERVER_URL}`. Prefer declaring it in `conformance.yaml`:
a scenario that talks to a mock should say which one.

`semconv_coverage(classify, model)` builds the reduction most wrappers want —
per registry span type, metric and event, which of its declared attributes the
run carried. It needs one thing the registry can't answer, which is how to
recognise a span of each type; the rest, including resolving the registry into
a coverage model, the runner does.

A domain's `config` is a `.weaver.toml` appended to the runner's
[defaults](src/opentelemetry/conformance/weaver-defaults.toml), which is where
findings a domain doesn't own are filtered out — an attribute the domain's
registry doesn't declare, but that the instrumentation is right to set, is not
a finding about it. Filter only those: something an implementation should fix
stays reported. `--weaver-config` replaces both.

`--data-command` replaces the built-in coverage reduction with a shell command
run after a complete (unfiltered) run: `"$1"` is the report directory, `"$2"`
the instrumented library, `"$3"` the instrumentation library, and the JSON it
prints becomes the data file. A non-zero exit or output that isn't JSON fails
the run.

```sh
--data-command 'jq -s --arg impl "$3" "{(\$impl): [.[].samples[].span.name]}" "$1"/*.json'
```

A directory overrides any of it by declaring `weaver:` or `server:` itself,
field by field — `server: {health: /ready}` keeps your server and only changes
where it is probed. Paths declared inside a `conformance.yaml` are relative to
that file, paths on the command line to your shell.

## Limitations

- **Only exercised against Python scenarios** so far. That is a convention of
  use rather than of design: a scenario gets everything it needs — OTLP
  endpoint and protocol, metric export interval, server URL — as environment
  variables and names its own `run` command, so another language only needs
  its own adapter.
- **Weaver live-check is the only backend**, so what it can't observe can't be
  checked. Expectations select spans only, by attribute value or kind — not by
  name, status or parent — and add count and attribute assertions on top of
  weaver's own conformance checks. Metrics and events are matched by name.
  Content isn't checked: whether a tool call round-tripped through the
  messages belongs in unit tests.
- **Servers are started, not managed.** A declared `server` must listen on
  `${PORT}` and answer a health endpoint. Anything with a different lifecycle
  — a container pool, a shared staging backend — you run yourself and pass the
  URL in with `--env`.
- **Scenarios run one at a time**, each under its own live-check.
