# opentelemetry-conformance

Runs scenario programs and checks their telemetry against expectations declared
in YAML and [Weaver live-check](https://github.com/open-telemetry/weaver). It
carries no semantic conventions of its own. You tell it which registry and
policies to validate against.

One session owns one Weaver process for the whole package. Scenarios export to a
stable local OTLP/gRPC capture endpoint, which assigns exports to the active
window and forwards the same requests to Weaver. Exports outside a window are
quarantined. The endpoint does not change between actions. Finalizing the
package stops the endpoint accepting exports and waits for the calls it had
already admitted, so nothing can arrive behind the quarantine check. The
runner, rather than Weaver or the scenario, owns action boundaries and
evaluates the per-scenario span, metric, and event assertions from captured
OTLP.

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
pytest path/to/directory
```

Each scenario prints one line — green `✔`, yellow `▲` for a violation under
`--report-only`, red `✖` — with the findings under it. Colour follows
`NO_COLOR`/`FORCE_COLOR` and is off when stdout isn't a terminal.

Pytest collects each `conformance.yaml` as one `package` item. All of its
scenarios, its one Weaver process, finalization, and data reduction stay in that
item, so xdist cannot split a package lifecycle across workers.

Or as a library, when you want the results rather than an exit code:

```python
with conformance_session(directory) as session:
    scenario = session.run("inference")
    package = session.finalize()
    print(scenario.failures, package.violations)
```

Anything the scenario got wrong, including a telemetry mismatch, crash, command
that won't start, or timeout, lands in `scenario.failures`. `finalize()` drains
and closes capture, stops Weaver once, and returns a `PackageReport` containing
the completed scenario reports, package failures, unexpected violations, and
Weaver's aggregate report. Repeated calls return the same report. Stale
`expected_violations` declarations land in `package.failures`. Problems with the
harness itself still raise.

- **Collecting data without failing.** Run everything and report semconv
  violations as warnings — `--report-only`. Useful for measuring attribute
  coverage across a whole repo, or for checking implementations you don't own.
  It only softens `package.violations`; a scenario that crashed, missed a
  declared span or broke `--data-command` still exits 1, because then there is
  nothing to measure.
- **Bringing up a new scenario.** Declare it with no expectations, run it,
  read the dumped report, and write the expectations from what you see.

A run writes two things, configured independently: a report bundle under
`--report-dir`, and one reduction over the whole run to `--data-file`
(`data.json` in the directory by default, and committed).

A scenario's capture is replaced when that scenario runs and left alone
otherwise. A filtered run therefore preserves the other diagnostic captures,
but does not rewrite `data.json`. The default path sits inside the conformance
directory, so sibling implementations with the same scenario names do not
collide:

```text
<conformance directory>/output/reports/
    scenarios/<scenario>.json
    weaver.json
    readiness.json
    unwindowed.json
```

Files under `scenarios/` contain normalized OTLP exports captured while that
scenario ran. They retain resource and instrumentation scope data, span
identity and timing, log identity and timing, and metric points and
temporality. `weaver.json` is Weaver's one aggregate report.
`readiness.json` holds the latest persistent batch's telemetry before its first
action. `unwindowed.json` appears only when telemetry arrives outside a
scenario window. Neither enters scenario assertions. A complete run cleans
stale scenario files and derives coverage from the normalized scenario captures
plus `unwindowed.json`; `weaver.json` supplies its findings. Readiness telemetry
does not count as coverage.

The reduction is the coverage this package computes. For each span a scenario
declares, it records the attributes the captured spans carried, plus captured
metrics and events and the findings from `weaver.json`:

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

`findings` is every violation Weaver reported over the aggregate run,
deduplicated on id, message, context and the signal it was reported on.
Weaver's lesser advice — `improvement`,
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
the built-in reduction when you want a different shape. Its first positional
argument is the report bundle directory above, not a directory of per-scenario
Weaver reports.

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

Several implementations can share telemetry expectations while keeping their
commands and configuration local. A named contract's only top-level key is
`scenarios`; each scenario may declare `spans`, `metrics` and `events`, but not
`run` or environment:

```yaml
scenario_contract: ../../contracts/http-client.yaml

scenarios:
  client:
    run: node client.js
```

The local scenario is merged over the contract by field, so it can replace one
expectation when an implementation intentionally has a different contract.
Relative paths start at the directory containing `conformance.yaml`.

A domain contract can instead use a `scenarios` list. Every entry must have
exactly `description`, a non-empty domain-owned `action` mapping, and a generic
`expect` mapping. Other contract fields are domain-owned metadata and ignored
by the generic runner:

```yaml
description: Shared HTTP client requests.
protocol: http
scenarios:
  - description: Sends one request.
    action:
      request: {method: GET, path: /items}
    expect:
      spans:
        - match: {kind: CLIENT}
          expect: {count: 1, attributes: {url.full: {present: true}}}
      events: []
```

The package declares one command template for the list:

```yaml
scenario_contract: ../../contracts/http-client.yaml
scenario_run: node client.js
```

The runner creates one scenario per contract entry and rejects local `scenarios`
overrides for this contract form. Each action gets a separate raw OTLP capture
window and scenario report. For a one-shot command, it serializes the selected
`action` as compact, key-sorted JSON in
`OTEL_CONFORMANCE_SCENARIO_ACTION`. Actions must be non-empty mappings with
string keys and JSON-representable values.

A contract that declares `readiness:` also gives the runner a whole action
table: readiness first, then every entry in declaration order. The runner
passes it as compact, key-sorted JSON in `OTEL_CONFORMANCE_SCENARIO_ACTIONS`
to a runner-managed `server:` and to a runner-driven process. A process that
answers actions rather than performing them needs every action the run may
reach, and the runner owns the table, so a package pointing at a contract of
its own is driven by that contract rather than by whichever one a driver
happens to ship.

A contract entry can split its expectations into named variants, one per side
of the exchange. A variant says who drives the action it describes:

```yaml
variants:
  client:
    description: The instrumented HTTP client sends the request.
    driver: instrumentation
  server:
    description: The instrumented HTTP server answers the request.
    driver: runner
```

```yaml
expect:
  client:
    spans: []
  server:
    spans: []
```

A package selects one:

```yaml
scenario_contract: ../../contracts/http.yaml
scenario_contract_variant: client
scenario_run: node scenario.js
```

The runner selects the requested variant before parsing its telemetry
expectations.

`driver` is what the package is really choosing. `instrumentation` means the
instrumented component initiates the action, so each action runs its own
process. `runner` means the runner drives one instrumented process through
every action in the batch, from outside. The package names the command and
the variant; how that command is run follows, and is never restated.

The catalog is one list of actions shared by every variant, so each entry
must carry expectations for every declared variant and for nothing else.
Otherwise a package selecting one side would be silently unjudged on an
action the other side covers.

A contract that declares no `variants` describes one way of running, and the
instrumented component drives it: every scenario is one-shot, exactly as it
was before roles existed. Entries with direct `spans`, `metrics`, or
`events` under `expect` remain valid there, as does selecting a variant by
expectation key alone. Local `scenarios` in a package are one-shot for the
same reason — they name their own command and no contract role applies.

A shared contract states what every implementation of it emits. One that
emits more says so in its own directory, so the metric check stays exact
without weakening the contract for everyone else:

```yaml
additional_metrics:
  - http.server.active_requests
```

Each name joins the `metrics` of every scenario that declares any. A
scenario that declares none stays unchecked. A metric only some actions
record — a request body size, say — says so instead of joining them all:

```yaml
additional_metrics:
  - name: http.server.request.body.size
    required: false
```

`required: false` adds an optional allow-list entry. Emitting that metric is not
an undeclared-metric failure, and omitting it is not a missing-metric failure.
Everything else in a declared metric list stays exact.

Spans an implementation adds are declared the same way, as `match` rules
appended to every scenario that declares spans:

```yaml
additional_spans:
  - match:
      kind: INTERNAL
```

A rule with no `expect.count` is an optional allow-list entry. It marks matching
extra spans as declared without requiring one. This fits spans whose count
follows the runtime rather than the contract. Give the rule a `count` to turn it
into an assertion.

### The runner-driven protocol

What follows is between the runner and a process it drives. Nothing here is
package configuration: a package asks for it by selecting a variant whose
`driver` is `runner`.

```yaml
scenario_contract_variant: server
scenario_run: [node, controller.js]
```

The runner then speaks `jsonl-v1` on that command's standard input and
output. It starts one controller, and therefore one measured process behind
that controller, for each selected consecutive batch that shares the
command. It waits for a `ready` record, sends one `action` record
per scenario, and closes stdin after the batch. Each record has `version`,
`type`, and an integer `sequence`; action records also carry the scenario name
and the selected action. The controller answers each action with
`action_complete` or `action_error`, then answers EOF with `stopped`.

The runner puts nothing of its own into the traffic the controller drives. A
correlation identifier would have to travel as a `traceparent`, which makes
what is measured the child of a remote parent: it changes the root of the
trace, the sampling decision the measured process inherits, and whether it
extracts context at all. Attribution comes from timestamps instead.

`ready` and `action_complete` carry `started_unix_nano` and
`completed_unix_nano`, stamped where the controller sent the exchange and
where it saw the answer. An instrumentation records what it measured before
it answers, so the aggregation interval holding that measurement can close
while the response is still travelling — and the runner reads the record
later still. Only the controller's own clock bounds the exchange.

Telemetry remains tentative until the controller acknowledges the action, its
positive expectations arrive, assigned exports drain, and a short quiet period
passes. Final checks happen only after `stopped`, process exit, and a final
capture drain.

An action window is bounded by the timestamps the instrumentation itself
reported, never by the order exports arrived in, so a cold runtime whose
first export is slow does not spill readiness telemetry into the first
action. What ran before the first action is the readiness window.

A span is placed by the interval between its start and its end, and its events
travel with it. A log record is placed by its own timestamp, falling back to
its observed timestamp. Spans of one trace describe one exchange, so a trace
whose spans fall in different windows is ambiguous and fails. So does a span
or record that reaches across a boundary, or lands in no window at all:
nothing is guessed.

Actions run one at a time, so a record that arrives while a later action is
running still belongs to whichever action its timestamps place it in. It can
never be counted toward the running one. It does mean the earlier action was
judged on a window that has since changed, so the batch fails there rather
than reporting either window.

A metric point must be safely assignable to one window. A monotonic sum or a
histogram must use delta temporality, and its interval may not cross another
action's response or the readiness boundary, because a point spanning two
exchanges belongs to neither. A gauge and a cumulative UpDownCounter report
the value at one instant, so their timestamp places them; only a delta
interval counts as an action's metric boundary.

An SDK reports on its own processors and exporters for as long as the process
runs, under the `otel.sdk.` metric namespace or an SDK-internal scope. That
describes the exporter the runner configured, so a scenario is neither
credited nor charged for it, and it never keeps an action from settling. The
raw exports still reach the report and Weaver.

Reports use stable zero-padded ordinal filenames, while CLI and pytest output
prefix `description` with its index; repeated descriptions do not merge
entries.

The protocol fails closed. A malformed, out-of-sequence, timed-out, or error
record aborts the batch. The failed action reports the protocol error and later
actions report that they were not executed; the runner never advances after an
uncertain result.

### Timeouts

Timeouts are seconds and can be overridden through the process environment:

| variable | default | covers |
| --- | ---: | --- |
| `OTEL_CONFORMANCE_SCENARIO_TIMEOUT` | 600 | setup and one-shot commands; persistent startup |
| `OTEL_CONFORMANCE_SCENARIO_WINDOW_TIMEOUT` | 10 | persistent readiness isolation, action response and settling, shutdown |
| `OTEL_CONFORMANCE_SCENARIO_SETTLE_DELAY` | 0.25 | quiet period after expected telemetry arrives |
| `OTEL_CONFORMANCE_CAPTURE_DRAIN_TIMEOUT` | 120 | in-flight OTLP forwarding |
| `OTEL_CONFORMANCE_WEAVER_STOP_TIMEOUT` | 120 | final Weaver report |
| `OTEL_CONFORMANCE_SERVER_STARTUP_TIMEOUT` | 30 | runner-managed server readiness |
| `OTEL_CONFORMANCE_SERVER_STOP_TIMEOUT` | 10 | runner-managed server shutdown |

`--scenario` takes the zero-padded ordinal, not the displayed label. To run the
first entry above, pass `--scenario 0000` rather than `[0] Sends one request.`.

`env` configures the scenario process. The real process environment wins over
it, so exporting a real key and base URL points a scenario at a real provider
instead of a mock. What the runner injects — the OTLP endpoint, the server URL
— wins over both, since those name what this run actually started.

### Known violations

Violations Weaver reports are failures unless the package declares them at the
top level with a reason:

```yaml
expected_violations:
  - id: genai_expected_attribute_missing
    context:
      operation: execute_tool
      missing_attribute: gen_ai.tool.call.id
    reason: The SDK does not expose the tool call id.
```

A declared violation Weaver stops reporting fails a complete run, so
suppressions do not outlive the gap that caused them. A filtered run still
fails on unexpected findings, but it cannot prove a package declaration is
stale.

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
runner_config:
  provider: example
```

`otel-conformance <dir>` and `pytest <dir>` both resolve it, so several
conventions domains coexist in one checkout — each directory gets its own
registry and reduction. A factory is `conformance_session` with defaults
applied; [`genai_conformance/__init__.py`](../gen-ai/runner/src/genai_conformance/__init__.py)
is a whole one. A directory naming no runner runs against whatever the command
line passes. The optional `runner_config` mapping reaches the selected factory
as `PackageSpec.runner_config`; the factory validates its own keys and values.

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
- **Scenarios run one at a time.** They share the package's Weaver live-check
  and use separate runner-owned capture windows.
