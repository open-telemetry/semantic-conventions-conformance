---
applyTo: "scenarios/database/**,tools/database/**"
---

# Code rules for scenarios/database, tools/database

- Keep each shared SQL action beside its cross-language telemetry expectations. Resolve the contract declared by `scenario_contract` for `runner_config.backend` and pass only the selected entry's `action` as JSON to the language adapter. The adapter translates it to the native client API without selecting a contract from connection variables or reading telemetry expectations. Redis uses named workloads with client-specific expectations instead.
- When a SQL workload exercises query sanitization and the sanitized output is stable across packages sharing the contract, assert the exact placeholder text in `db.query.text`. A presence-only check would also accept leaked literals.
- Redis scenarios use `DATABASE_NAME` as the logical database index and use `DATABASE_USER` and `DATABASE_PASSWORD` to authenticate only when the password is nonempty. The default fixture must work on database zero without authentication.
