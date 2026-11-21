# Browser conformance scenarios

What a browser instrumentation emits from a real page, checked against the
semantic conventions and recorded as committed coverage.

```text
js/<browser>/<instrumentation>/
    conformance.yaml    how to run it
    data.json           the coverage it produced, committed
```

These scenarios use [`browser-conformance`](../../tools/browser/runner), which
pins the upstream registry independently of the HTTP domain. It checks
`exception` and `browser.web_vital` events without classifying spans.

[`tools/js/browser-runner`](../../tools/js/browser-runner), which the HTTP
Fetch scenario also uses, serves each page and relays its OTLP exports to the
runner. See [`js/`](js/README.md) for the build root and what is measured.

## Not covered yet

Only three of the nine modules in `@opentelemetry/browser-instrumentation`
0.8.1 are measured: `errors`, `console` and `web-vitals`. `navigation`,
`navigation-timing`, `resource-timing`, `user-action`, `fetch` and `xhr` are
not. Only events are checked, the scenarios produce no spans or metrics.
