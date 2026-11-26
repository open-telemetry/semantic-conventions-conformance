# Browser conformance

Run a browser conformance directory against the OpenTelemetry semantic
conventions.

```sh
pip install -e tools/runner -e tools/browser/runner
browser-conformance path/to/directory
```

The runner checks `exception` and `browser.web_vital` events. Its classifier
returns no span types because this domain measures events only. Use an
HTTP-domain scenario like
[HTTP Fetch](../../../scenarios/http/js/fetch/opentelemetry-fetch/client/conformance.yaml)
to measure spans from browser HTTP instrumentation.

[`versions.env`](src/browser_conformance/versions.env) pins the registry
used by this runner. The coverage site combines declarations by signal type
and name. Before changing this pin separately, check that shared signals
such as `exception` still have the same declaration in the other runners.
