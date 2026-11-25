---
applyTo: "scenarios/database/**,tools/database/sql-test-client/**"
---

# Code rules for scenarios/database, tools/database/sql-test-client

- An indexed SQL workload executes the `action` paired with its selected telemetry expectations, supplied as JSON in `OTEL_CONFORMANCE_SCENARIO_ACTION`. The `scenario_contract` selection is authoritative; the adapter does not select another contract or derive the operation from the entry's index. Named telemetry-only workloads do not use this action path.
