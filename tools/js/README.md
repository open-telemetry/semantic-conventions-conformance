# JavaScript conformance scenarios

Everything a Node scenario shares: the support every scenario needs whatever
domain it measures, the SDK a library-instrumentation scenario configures for
itself, and the command that installs a Node build.

```text
domains/<domain>/js/           a domain's npm build root — workspaces and the lockfile
tools/js/scenario-support/  what a scenario needs before any telemetry
tools/js/scenario-sdk/      the SDK a library-instrumentation scenario owns
tools/js/src/               `otel-conformance-js`, the launcher
tools/js/tests/             the launcher's tests
```

## A build root per domain

A domain's Node scenarios are one npm workspace, rooted at its own
`domains/<domain>/js` — today only
[`domains/http/js`](../../domains/http/js). `otel-conformance-js` finds it
by searching upwards from the scenario directory for `package-lock.json`, so a
scenario file says nothing about how deep it is nested. Within a build,
packages are grouped by the library they instrument, so
`express/opentelemetry-express` sits beside the Express workload it launches.

The packages here are shared by depending on them by path, which npm installs
as copies rather than as links. That is what the build root's `.npmrc` asks
for, and it is not a detail: npm links a local package by symlinking it, and
Node then resolves that package's own imports from where it really lives —
outside the build, where nothing is installed. Copies put a shared package and
its dependencies in one tree. The cost is that editing a file here has no
effect on a scenario until the build root is installed again — which a run
always does, since every package's `setup:` installs before it runs, so a
scenario cannot measure a stale copy of what is here.

## What a scenario shares

[`scenario-support/`](scenario-support) carries no OpenTelemetry dependency at
all, which is the point: a scenario measuring an auto-instrumentation runtime
must load only what that runtime brings, so what every scenario needs — the
runner's environment, and the driver's shutdown protocol — cannot live beside
the SDK. Node has such a runtime in `@opentelemetry/auto-instrumentations-node`,
so the split earns itself here even though nothing measures that runtime yet.

[`scenario-sdk/`](scenario-sdk) is the other half: the SDK, the OTLP exporter
and the flush on shutdown, for scenarios measuring explicit library
instrumentation. It takes the instrumentations to register and the workload to
run, and reads everything else — the endpoint, its protocol, the export
interval — from the environment the runner injected.

The workload arrives as a function rather than as a promise, because a Node
instrumentation patches a module as it is required and one required earlier is
never patched at all. Passing a function is what keeps the library under test
from being loaded before the instrumentation measuring it is registered:

```js
runScenario({ instrumentations: [new ExpressInstrumentation()] }, () =>
  require("@otel-conformance/express-scenarios").serve(),
);
```

## CommonJS, not ESM

Scenarios are CommonJS because that is what Node's instrumentations can
actually see. `@opentelemetry/instrumentation-express` patches Express through
`require`, and an ESM `import` of the same package bypasses that entirely: a
measured run under ESM produced a bare `GET` server span with no `http.route`
and no Express spans at all, and recovering them needed the deprecated
`--experimental-loader` hook on every command line. Under CommonJS, "register
before the library is loaded" is a plain ordering of `require` calls.

## `otel-conformance-js`

Installs a Node conformance build, so no `conformance.yaml` restates how npm is
invoked:

```yaml
setup: otel-conformance-js install
```

That is the only Node step a scenario file cannot name portably. Running one is
`node`, an executable everywhere; `npm` is a shell script with a `.cmd` shim on
Windows, and the runner starts a declared command directly rather than through
a shell, so a bare `npm ci` in `setup:` fails there.

`install` runs `npm ci` at the build root, so a scenario gets the versions the
committed lockfile pins rather than whatever resolves today, and every package
in the build is installed once however deep its own directory sits.
