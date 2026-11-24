---
applyTo: ".github/**,scenarios/browser/**"
---

# Code rules for .github, scenarios/browser

- While `@opentelemetry/browser-instrumentation` requires the 0.222 SDK line, keep the browser-event workspace's API, instrumentation, log exporter, and logs SDK pins compatible and exclude them from independent Renovate updates. Move the pins together when the instrumentation supports the newer line.
