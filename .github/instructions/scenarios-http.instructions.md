---
applyTo: "scenarios/http/**"
---

# Code rules for scenarios/http

- Keep HTTP workload code in the library's shared `scenarios/` directory free of OpenTelemetry setup and instrumentation.
- HTTP conformance workloads must exercise the shared HTTP exchange contract rather than substitute language- or client-specific exchanges.
- An HTTP JavaScript scenario package that uses an unpublished repository helper declares its own path dependency on that helper rather than relying on a registry range satisfied by a sibling workspace.
