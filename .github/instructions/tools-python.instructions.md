---
applyTo: "tools/python/**"
---

# Code rules for tools/python

- Before normal SDK shutdown, the Python launcher flushes traces and logs, waits for both, then flushes metrics within the same 15-second budget; a failure or timeout fails the scenario. Direct `opentelemetry-instrument` launches are outside this lifecycle.
