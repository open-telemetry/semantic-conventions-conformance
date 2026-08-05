# OpenTelemetry Semantic Conventions Conformance

Automated conformance validation of library instrumentations against the
[OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/).

> [!NOTE]
> This repository is still being populated. The conformance framework, CI, and
> scenarios are being migrated in from a
> [prototype](https://github.com/trask/semantic-conventions-conformance-prototype)
> in stages, tracked in
> [#6](https://github.com/open-telemetry/semantic-conventions-conformance/issues/6).

## Domains

Each top-level directory contains conformance scenarios for a specific
semantic convention domain:

- `http/`: [HTTP](https://opentelemetry.io/docs/specs/semconv/http/) semantic conventions
- `genai/`: [Generative AI](https://github.com/open-telemetry/semantic-conventions-genai) semantic conventions

## How it works

Each domain ships its own runnable assets directly under `<domain>/`, and the
shared Python tooling in `src/semconv_conformance/` provides the CLI scenario
runners and dashboard generators.

The general pattern across domains:

1. Domain-specific local **scenario infrastructure** provides deterministic
   inputs where needed (for example, a mock LLM server for GenAI).
2. A language-specific **scenario app** exercises the instrumented library or
   framework.
3. [**Weaver `registry live-check`**](https://github.com/open-telemetry/weaver)
   validates exported telemetry against the official semantic conventions
   registry and reports coverage statistics.
4. Results are committed as `data-<eco>.json` files and rendered into coverage
   dashboards.

```text
        [Mock LLM Server]*
               ▲
               │
Scenario App  ──OTLP──▶  Weaver registry live-check  ──▶  Results JSON
```

<sub>\* GenAI only: a local mock LLM server serves deterministic responses for
OpenAI, Anthropic, Google, AWS Bedrock, and Cohere APIs, so scenarios need no
API keys or network access. HTTP scenarios exercise instrumented clients /
servers / middleware directly.</sub>

## Maintainers

- [Christophe Kamphaus](https://github.com/kamphaus), Independent
- [Jay DeLuca](https://github.com/jaydeluca), Grafana Labs
- [Josh Suereth](https://github.com/jsuereth), Google
- [Liudmila Molkova](https://github.com/lmolkova), Google
- [Trask Stalnaker](https://github.com/trask), Microsoft

For more information about the maintainer role, see the [community repository](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#maintainer).

## Approvers

- None

For more information about the approver role, see the [community repository](https://github.com/open-telemetry/community/blob/main/guides/contributor/membership.md#approver).

## License

[Apache 2.0](LICENSE)
