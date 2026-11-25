---
applyTo: "tools/database/runner/src/database_conformance/**"
---

# Code rules for tools/database/runner/src/database_conformance

- A database readiness probe succeeds only when the backend is ready for fixture initialization, not merely when it accepts a connection or login. A not-ready reply must fail the startup gate: for example, SQL Server's `model` must be ready for `CREATE DATABASE`, and an exit-status gate needs `sqlcmd -b`, `redis-cli -e`, or equivalent reply validation to detect server errors.
