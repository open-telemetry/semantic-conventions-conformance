# JavaScript conformance scenarios

Everything a Node scenario shares: the support every scenario needs whatever
domain it measures, the SDK a library-instrumentation scenario configures for
itself, and the command that installs a Node build.

```text
scenarios/<domain>/js/      a domain's npm build root — workspaces and the lockfile
tools/js/scenario-support/  what a scenario needs before any telemetry
tools/js/scenario-sdk/      the SDK a library-instrumentation scenario owns
tools/js/browser-runner/    runs a browser scenario's page in headless Chrome
tools/js/src/               `otel-conformance-js`, the launcher
tools/js/tests/             the launcher's tests
```

## A build root per domain

A domain's Node scenarios are one npm workspace, rooted at its own
`scenarios/<domain>/js` —
[`scenarios/http/js`](../../scenarios/http/js) and
[`scenarios/gen-ai/js`](../../scenarios/gen-ai/js). `otel-conformance-js` finds it
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

After the workload returns, it starts trace and log flushes and awaits both,
then flushes metrics, then performs normal SDK shutdown. The flush phases
share a 15-second budget, and a timeout or failed flush fails the scenario.

The workload arrives as a function rather than as a promise, because a Node
instrumentation patches a module as it is required and one required earlier is
never patched at all. Passing a function is what keeps the library under test
from being loaded before the instrumentation measuring it is registered:

```js
runScenario({ instrumentations: [new ExpressInstrumentation()] }, () =>
  require("@otel-conformance/express-scenarios").serve(),
);
```

## Browser scenarios

[`browser-runner/`](browser-runner) runs a scenario whose code has to execute
in a page. `index.js` is the Node half: it bundles the page with esbuild,
serves it, and opens it in the Chrome the machine already has through
`playwright-core`, falling back to Playwright's own Chromium. `page.js` is the
page half, which hands the workload to `index.js` and says where to export:

```js
exposeScenario(async ({ exchanges }) => {
  // register instrumentations exporting to exportUrl("traces"), then
  return drive(location.origin, exchanges);
});
```

Everything is one origin, since the runner's OTLP/HTTP bridge does not answer
a CORS preflight. Exports under `/_otel-conformance/v1/` are relayed to the
endpoint the runner injected, with a `Content-Length` because the bridge
refuses a chunked body, and an export it does not accept fails the run. Any
other path is proxied to `MOCK_SERVER_URL` when there is one, so a request
keeps the contract's path and query. A scenario declares
`otlp_protocol: http/protobuf`, as a browser cannot export gRPC.

A run is bounded: an error thrown while the page loads fails it at once with
that error, the workload gets 30 seconds, and the page's console and errors go
to stderr.

`browser-runner/tracing` exports `runWithTracing`, which registers the supplied
instrumentations and runs a workload with a provider and OTLP exporter. It
waits up to 20 seconds for the expected span count and flushes the provider.
Fetch and XMLHttpRequest use this setup. Their decoded-span integration tests
share `assertSelectedHttpClientSpan` from `browser-runner/testing`, including
the mock server, export receiver, and protobuf decoder.

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

`relock` works the other way round: from anywhere in the repository, it
regenerates every committed `package-lock.json` under `scenarios/` and `tools/`
with `npm install --package-lock-only --ignore-scripts`, which installs nothing,
runs no scripts, and changes only what the manifests require. Before invoking
npm, it removes the cached snapshots of copied `file:` packages and their
nested dependency entries from the lockfile so npm reads their current
manifests and resolves their dependencies. Registry package pins outside
those subtrees remain in place. If regeneration fails, the project's
original lockfile is restored byte for byte. CI runs `relock` on Renovate
PRs and commits the result. Run it by hand when `npm ci` reports that the
lockfile is out of sync:

```sh
otel-conformance-js relock
```
