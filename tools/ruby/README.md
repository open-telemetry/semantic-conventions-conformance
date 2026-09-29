# Ruby conformance scenarios

The Ruby tooling keeps package installation, process launch, scenario lifecycle,
and explicit OpenTelemetry setup in separate pieces.

```text
scenarios/<domain>/ruby/      a domain's Ruby scenario packages
tools/ruby/scenario-support/  environment and stdin-EOF lifecycle
tools/ruby/scenario-sdk/      explicit instrumentation and telemetry SDK setup
tools/ruby/src/               `otel-conformance-ruby`, the launcher
tools/ruby/tests/             the launcher's tests
```

## Package layout

Each scenario package owns a `Gemfile` and committed `Gemfile.lock`. The
launcher searches upward from the current scenario directory for the nearest
directory containing both files. A package can use the shared gems by a path
relative to its package root:

```ruby
gem "otel-conformance-scenario-support",
    path: "../../../../../../tools/ruby/scenario-support"
gem "otel-conformance-scenario-sdk",
    path: "../../../../../../tools/ruby/scenario-sdk"
gem "opentelemetry-instrumentation-net_http"
```

Run `bundle lock` when dependencies change and commit the result. Installation
is frozen under `vendor/bundle` below the package root, with shared gems
disabled. Installation and lookup stay inside the package bundle instead of
using user-wide or system gems. CI uses the same location through
`ruby/setup-ruby`'s Bundler cache.

## Launcher

```yaml
setup: otel-conformance-ruby install

scenarios:
  client:
    run: otel-conformance-ruby run client.rb
```

`install` runs Bundler from the package root with the committed lockfile.
`run <entry.rb> [args...]` resolves the entry point from the invoking scenario
directory, then uses `bundle exec ruby` with the same Gemfile and generated
bundle. Both commands locate Ruby and Bundler through `PATH`, including Windows
Bundler shims, and return the child process's exit status.

`relock` is for maintainers: from anywhere in the repository, it runs
`bundle lock` (without `--update`) for every committed `Gemfile.lock` under
`scenarios/` and `tools/`, with the frozen setting that `install` and `run` use
switched off. That way only what the Gemfiles and the `path:` gems require
changes. CI runs it on Renovate PRs and commits the result. Run it by hand when
a frozen install reports that the lockfile needs updating:

```sh
otel-conformance-ruby relock
```

## Shared Ruby APIs

`otel-conformance-scenario-support` has no OpenTelemetry dependency:

```ruby
require "opentelemetry/conformance/scenario_support"

endpoint =
  OpenTelemetry::Conformance::ScenarioEnvironment.require(
    "OTEL_EXPORTER_OTLP_ENDPOINT"
  )
OpenTelemetry::Conformance::ScenarioLifecycle.wait_for_eof
```

The SDK gem is for scenarios that register library instrumentation explicitly.
It configures OTLP/HTTP protobuf exporters for traces and metrics, registers
only the named instrumentation, and flushes and shuts down both providers even
when the workload fails:

```ruby
require "opentelemetry/instrumentation/net/http"
require "opentelemetry/conformance/scenario_sdk"

OpenTelemetry::Conformance::ScenarioSdk.run(
  instrumentation: "OpenTelemetry::Instrumentation::Net::HTTP"
) do
  # Start the workload, then wait for the driver to close standard input.
end
```

Keep `scenario-support` separate from `scenario-sdk`: a scenario measured by an
automatic instrumentation runtime needs the environment and EOF protocol but
must not load a second OpenTelemetry SDK.
