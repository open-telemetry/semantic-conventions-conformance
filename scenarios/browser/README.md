# Browser conformance scenarios

What a browser instrumentation emits from a real page, checked against the
semantic conventions and recorded as committed coverage.

```text
js/<browser>/<instrumentation>/
    conformance.yaml    how to run it
    data.json           the coverage it produced, committed
```

No runner package covers browser conventions yet. These scenarios declare
`runner: http-conformance` because that runner pins the upstream registry
([`versions.env`](../../tools/http/runner/src/http_conformance/versions.env)),
which defines the `exception` and `browser.web_vital` events, and because its
span classifier only acts on spans carrying `http.request.method`. The report
files a target by its path, so these appear under `browser`.

[`tools/js/browser-launcher`](../../tools/js/browser-launcher) serves each page
and relays its OTLP exports to the runner. See [`js/`](js/README.md) for the
build root and what is measured.

## Not covered yet

Only three of the nine modules in `@opentelemetry/browser-instrumentation`
0.8.1 are measured: `errors`, `console` and `web-vitals`. `navigation`,
`navigation-timing`, `resource-timing`, `user-action`, `fetch` and `xhr` are
not. Only events are checked, the scenarios produce no spans or metrics.
