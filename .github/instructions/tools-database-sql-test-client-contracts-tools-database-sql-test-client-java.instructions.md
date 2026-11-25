---
applyTo: "tools/database/sql-test-client/contracts/**,tools/database/sql-test-client/java/**"
---

# Code rules for tools/database/sql-test-client/contracts, tools/database/sql-test-client/java

- Shared SQL contracts keep each backend action beside its generic telemetry expectations. Language adapters translate the selected JSON action into client calls rather than defining a separate workload.
