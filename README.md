# OpenTelemetry Semantic Conventions Conformance

Does an instrumentation actually emit what the semantic conventions say it
should? This repo answers that the same way for every library, every
implementation and every language: run a small program that exercises the
library, collect what it emits through
[Weaver live-check](https://github.com/open-telemetry/weaver), and check it
against expectations declared in YAML.

| | |
| --- | --- |
| [`tools/runner/`](tools/runner) | the runner. Generic — it carries no semantic conventions of its own |
| [`tools/gen-ai/`](tools/gen-ai) | what makes a run a *GenAI* run: the registry pin, the advice policies, and a mock LLM server so scenarios are deterministic without cassettes |
| [`tools/http/`](tools/http) | the same for HTTP: the upstream registry pin, and the test client that drives both sides of the domain |
| [`tools/java/`](tools/java) | what every JVM scenario shares, in any domain: the launcher that builds and runs one, the Gradle convention plugins, and the SDK bootstrap |
| [`tools/js/`](tools/js) | what every Node scenario shares: the launcher that installs a build, and the SDK bootstrap |
| [`tools/dotnet/`](tools/dotnet) | what every .NET scenario shares: the launcher that builds and runs one, the shutdown protocol every scenario needs, and the SDK bootstrap the ones measuring library instrumentation own |
| [`tools/report/`](tools/report) | the report every scenario's coverage is joined into, and the [site](docs) that reads it |
| [`scenarios/gen-ai/`](scenarios/gen-ai) | the GenAI scenarios and the coverage they produce |
| [`scenarios/http/`](scenarios/http) | the HTTP scenarios and the coverage they produce |

A conformance directory names the wrapper it wants under `runner:`, so one
command runs any of them:

```sh
pip install -e tools/runner -e tools/gen-ai/mock-server -e tools/gen-ai/runner
otel-conformance path/to/directory --report-only
```

See the [runner's README](tools/runner/README.md) for what a scenario and its
`conformance.yaml` look like.

What every scenario currently emits is published at
[open-telemetry.github.io/semantic-conventions-conformance](https://open-telemetry.github.io/semantic-conventions-conformance/).

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
