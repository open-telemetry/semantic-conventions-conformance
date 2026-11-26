---
applyTo: "scenarios/**"
---

# Conformance scenarios

- Each conformance directory commits the runner-generated `data.json` from a complete run of its current scenarios and pinned instrumentation. A `--report-only` run can refresh the snapshot without treating Weaver findings as run failures.

- Shared workloads exercise the library without selecting instrumentation or initializing OpenTelemetry. Any explicit setup belongs to the implementation-specific launcher or agent so the same workload can run unchanged under another implementation.
