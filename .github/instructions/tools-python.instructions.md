---
applyTo: "tools/python/**"
---

# Code rules for tools/python

- Python scenarios that need programmatic SDK configuration use `otel-conformance-python` to install OTLP providers, with the entry program selecting instrumentation. On normal shutdown, the launcher waits for traces and logs to force-flush before force-flushing metrics, all within one 15-second budget. A flush failure or timeout fails the scenario; direct `opentelemetry-instrument` runs are outside this lifecycle.
