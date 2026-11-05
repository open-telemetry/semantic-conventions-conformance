# SQL Server JDBC scenarios

The database runner starts SQL Server Developer edition and accepts Microsoft's
container license through the required `ACCEPT_EULA=Y` setting. It applies the
[scenario schema](../../../../tools/database/runner/src/database_conformance/sql_server.sql)
before measured processes start; the schema creates the workload objects but
does not seed rows.

Both JDBC instrumentation modes use the SQL Server driver's
`encrypt=true;trustServerCertificate=true` options for the test container's
self-signed certificate. The action and expected telemetry for each JDBC
operation live together in the
[SQL Server contract](../../../../tools/database/sql-test-client/contracts/sql_server.yaml).
