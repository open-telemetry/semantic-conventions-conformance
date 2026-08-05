# OpenTelemetry Semantic Conventions Conformance

Automated conformance validation of library instrumentations against the
[OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/).

> [!NOTE]
> This repository is still being populated. Scenarios are being migrated in from
> a [prototype](https://github.com/trask/semantic-conventions-conformance-prototype)
> one language and domain at a time, tracked in
> [#6](https://github.com/open-telemetry/semantic-conventions-conformance/issues/6).

## How it works

1. A language-specific **scenario app** exercises an instrumented library or
   framework and exports its telemetry over OTLP.
2. [**Weaver `registry live-check`**](https://github.com/open-telemetry/weaver)
   validates that telemetry against the official semantic conventions registry
   and reports which attributes were actually emitted.
3. The observed coverage is written to a committed `data-<eco>.json` file next
   to the scenario.

```text
Scenario App  ──OTLP──▶  Weaver registry live-check  ──▶  data-<eco>.json
```

CI re-runs the scenarios affected by a pull request and fails if any committed
`data-<eco>.json` no longer matches what the instrumentation produces, so the
recorded results stay honest as upstream libraries change.

## Layout

Conformance scenarios live in one top-level directory per semantic convention
domain, with one subdirectory per language and library:

- [`http/`](http/): [HTTP](https://opentelemetry.io/docs/specs/semconv/http/)
  semantic conventions

Additional domains — starting with
[Generative AI](https://github.com/open-telemetry/semantic-conventions-genai) —
are migrating in as tracked in
[#6](https://github.com/open-telemetry/semantic-conventions-conformance/issues/6).

The shared Python tooling in `src/semconv_conformance/` provides the scenario
runner and the CI matrix generator. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for local setup, how to run a single
scenario, and how to add a library, ecosystem, or language.

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
