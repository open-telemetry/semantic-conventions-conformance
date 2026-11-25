---
applyTo: "scenarios/database/**,tools/database/runner/**,tools/database/sql-test-client/**"
---

# Code rules for scenarios/database, tools/database/runner, tools/database/sql-test-client

- Shared SQL contracts keep each backend action beside its telemetry expectations, and the language helper translates the supplied JSON action into client API calls.
