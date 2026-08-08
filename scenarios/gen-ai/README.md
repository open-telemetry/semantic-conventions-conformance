# GenAI scenarios

Scenario programs checked against the
[GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai).
What makes a run a *GenAI* run — the registry pin, the advice policies, the
mock LLM server — lives in [`tools/gen-ai`](../../tools/gen-ai); the
[runner](../../tools/runner) carries none of it.

## Running

```sh
pip install -e tools/runner -e tools/gen-ai/mock-server -e tools/gen-ai/runner
otel-conformance scenarios/gen-ai/python/openai/opentelemetry --report-only
otel-conformance scenarios/gen-ai/python/openai/opentelemetry --report-only --scenario inference
```

Each directory declares `runner: genai-conformance`, which is what fills the
registry and the advice policies in. `genai-conformance <dir>` is the same
thing with that wrapper pinned rather than read from the file. Every flag
still works, and still wins — a repo checking its own working tree points the
registry at it:

```sh
genai-conformance path/to/directory --registry ./model
```

You also need the `weaver` binary on `PATH`, at the version
[`versions.env`](../../tools/runner/src/opentelemetry/conformance/versions.env)
pins; the registry pin is in
[`tools/gen-ai/runner/…/versions.env`](../../tools/gen-ai/runner/src/genai_conformance/versions.env).

## The scenario tree

```
scenarios/gen-ai/<language>/<library>/
    scenarios/              the programs — one copy, shared
    <instrumentation>/      conformance.yaml, pyproject.toml, data.json
```

`<library>` is the client library being exercised; `<instrumentation>` is whose
instrumentation produced the telemetry — `opentelemetry`, `openinference`,
`reference` (the hand-written implementation the semconv repo maintains), or
`native` when the library instruments itself.

Those directory names are short labels for reading the tree. What a run is
actually about is declared in each `conformance.yaml`, where `library:` and
`instrumentation:` name the real packages:

```yaml
instrumented_library: openai
instrumentation_library: opentelemetry-instrumentation-genai-openai
```

Nothing derives one from the other: the runner never reads a path for meaning,
so a directory can be renamed or a scenario moved without changing what the
results say produced them.

**The programs live once, under the library.** Every implementation runs the
same file:

```yaml
run: uv run --project . opentelemetry-instrument python ../scenarios/inference.py
```

`--project .` runs it in the implementation directory's own environment, which
uv syncs from the `pyproject.toml` there. Each implementation gets its own, so
zero-code never finds a neighbour's instrumentation installed — which is both
what makes the results comparable and the constraint on adding one: an
implementation's environment must hold only its own instrumentation, or
someone else's spans land in the results. A scenario program therefore never
names an instrumentation.

`reference` is the exception, and runs its own program: there the
instrumentation *is* hand-written around the library calls, so there is nothing
to share.

Each implementation directory holds its `conformance.yaml` (how to run the
programs), a `pyproject.toml` declaring its dependencies, and a committed
`data.json` recording what the run actually emitted.

## Measuring, not testing

The runner can assert span counts, required metrics and the rest. **Nothing
here does.** Those are tests, and a test belongs with the instrumentation it
covers — `opentelemetry-python-genai` for the `opentelemetry` implementation,
`semantic-conventions-genai` for `reference`. What this repo owns is the
measurement. Runs are `--report-only` for the same reason: a semconv finding
is a result to read, not a build to break. A scenario that crashed or missed
something it declared still fails — the harness has no measurement to report.

`expected_violations` is the exception, and stays: a divergence someone has
looked at and written a reason for is a different fact from one nobody has
seen yet, and only the file can carry that distinction.

> The trees under `python/` today are **demos** — they show the layout and are
> not maintained conformance results.
