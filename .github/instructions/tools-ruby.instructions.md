---
applyTo: "tools/ruby/**"
---

# Code rules for tools/ruby

- Ruby's environment and process-lifecycle support stays separate from SDK setup. An automatically instrumented scenario uses that support without loading a second OpenTelemetry SDK.
