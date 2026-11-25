---
applyTo: "tools/python/**"
---

# Code rules for tools/python

- Before normal SDK shutdown, the programmatic Python launcher force-flushes traces and logs and waits for both before force-flushing metrics. All flushes share one 15-second budget, and a failure or timeout fails the scenario; direct `opentelemetry-instrument` runs are outside this launcher's control.
