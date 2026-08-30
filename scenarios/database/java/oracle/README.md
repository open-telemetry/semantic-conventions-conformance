# Oracle JDBC scenarios

The database runner starts a pinned Oracle Database Free `slim-faststart`
container and waits for `healthcheck.sh`. Startup allows three minutes by
default; set `OTEL_CONFORMANCE_ORACLE_STARTUP_TIMEOUT` to a positive number of
seconds to override it.

The runner creates the `conformance` application user in `FREEPDB1` and applies
the [scenario schema](../../../../tools/database/runner/src/database_conformance/oracle.sql)
before measured processes start. The schema creates an empty table and a no-op
stored procedure. SQL*Plus exits with failure on SQL or operating-system errors.

Both JDBC instrumentation modes use the `ojdbc11` driver. The Java agent uses
`jdbc:oracle:thin:@//host:port/FREEPDB1`; JDBC library instrumentation prefixes
that URL with `jdbc:otel:`.

The [Oracle contract](../../../../tools/database/sql-test-client/contracts/oracle.yaml)
defines direct and prepared queries, a two-insert batch, and a stored-procedure
call. The direct query uses `CASE` to return a number rather than a SQL boolean,
and the procedure uses JDBC escape syntax, `{call conformance.noop()}`.
Expected telemetry uses `db.system.name=oracle.db` and the lowercase
`db.namespace=freepdb1`.
