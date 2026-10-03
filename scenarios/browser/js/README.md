# Browser conformance scenarios in JavaScript

```text
chromium/scenarios/                               what each page does, no OTel
chromium/opentelemetry-browser-instrumentation/   run.js, pages/, conformance.yaml
```

This directory is the build root: one npm workspace with a committed lockfile.

Each scenario opens one page in headless Chrome, and each page registers one
module of `@opentelemetry/browser-instrumentation`, so a scenario's report holds
one instrumentation scope:

| Scenario     | Module                    | Event               |
| ------------ | ------------------------- | ------------------- |
| `errors`     | `experimental/errors`     | `exception`         |
| `console`    | `experimental/console`    | `browser.console`   |
| `web_vitals` | `experimental/web-vitals` | `browser.web_vital` |

`browser.console` is not in the registry at the pinned version, so its findings
are recorded rather than its attributes.

The scenarios use the Chrome already installed on the machine, on CI the one in
the `ubuntu-latest` image, so the browser version is not pinned. Set
`OTEL_CONFORMANCE_BROWSER_CHANNEL=msedge` to use Edge instead.
