# genai-conformance

What makes a run a *GenAI* run. The [runner](../../runner) knows how to execute
scenarios and check them; everything specific to these semantic conventions is
here.

The package is a [`Domain`](../../runner/README.md#wrapping-it-for-your-repo)
and three files:

| | |
| --- | --- |
| [`versions.env`](src/genai_conformance/versions.env) | the pinned registry commit, managed by Renovate. The weaver pin is shared, in the runner |
| [`policies/`](src/genai_conformance/policies) | advice policies weaver live-check runs on top of the registry's own checks |
| [`_coverage.py`](src/genai_conformance/_coverage.py) | how to recognise a GenAI span type |

```sh
pip install -e tools/runner -e tools/gen-ai/mock-server -e tools/gen-ai/runner
otel-conformance path/to/directory --report-only
```

A directory declaring `runner: genai-conformance` gets the registry and the
policies filled in. `genai-conformance <dir>` is the same CLI with that
pinned instead of read from the file; every flag still works, and still wins.
Or, as a library, `genai_session` is `conformance_session` with the same
defaults applied:

```python
with genai_session(directory) as session:
    report = session.run("inference")
```

The [mock LLM server](../mock-server) is *not* one of those defaults — a
directory declares it under `server:`, so a file that references
`${MOCK_SERVER_URL}` says where it comes from.

Nothing here is on PyPI, so install it from a checkout.

## What a run reduces to

The runner's own reduction keys `data.json` on the spans a scenario *declares*,
which is all it can do without knowing the conventions. `genai_session`
replaces it: every span is classified into a registry span type, and the file
records which of that type's attributes were present.

```json
{"spans": {"gen_ai.inference.client": ["gen_ai.input.messages", "gen_ai.operation.name", "…"]}}
```

Two implementations of one library diff directly.

What a span type declares comes from the registry — see the runner's
[coverage model](../../runner/README.md#the-coverage-model).
Recognising a span is the one thing the registry can't answer — every span type
carries the whole `gen_ai.operation.name` enum — so which operation names mean
which span type is stated in `_coverage.py`. That, the pin and the policies are
the whole of what this package adds.

The file records only what the registry knows: an attribute it doesn't declare
doesn't appear, and neither do metrics or events unless the run produced them.
Pass `build_data=opentelemetry.conformance.coverage` for the runner's generic
reduction instead.

## The registry

`versions.env` pins a `semantic-conventions-genai` commit, which the runner
downloads into `$SEMCONV_CACHE` (default `~/.cache/otel-conformance/semconv`)
on first use. Its `model/manifest.yaml` names the upstream
`semantic-conventions` registry as a git URL, so weaver fetches and resolves
that itself.

One thing is still patched: the draft-07 `$ref` in
`gen-ai-tool-definitions.json` is rewritten to a plain object, because weaver's
rego engine won't fetch it at eval time.

A repo checking its own working tree overrides just the registry:

```sh
otel-conformance path/to/directory --registry ./model
```
