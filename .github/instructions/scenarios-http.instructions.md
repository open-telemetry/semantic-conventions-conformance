---
applyTo: "scenarios/http/**"
---

# Code rules for scenarios/http

- HTTP server workloads declare matching routes in their framework's native routing model, using native parameterized mappings where supported. The shared contract specifies concrete exchanges, not a route-template syntax to implement across frameworks.

- HTTP client and server scenarios use separate conformance directories, even when they share a library and instrumentation. Coverage aggregates all telemetry in a directory, so combining the two sides can hide signals emitted on the wrong side.
