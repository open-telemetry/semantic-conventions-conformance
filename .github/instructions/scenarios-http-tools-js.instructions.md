---
applyTo: "scenarios/http/**,tools/js/**"
---

# Code rules for scenarios/http, tools/js

- Browser HTTP clients use the shared tracing harness for provider setup and export tracking. Exclude readiness exchanges from the expected workload span count and exclude the OTLP relay route from client instrumentation.
