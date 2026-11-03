# Oracle JDBC scenarios

The database runner starts a pinned Oracle Database Free `slim-faststart`
container and waits for `healthcheck.sh`. Startup allows three minutes by
default; set `OTEL_CONFORMANCE_DATABASE_STARTUP_TIMEOUT` to a finite positive
number of seconds in the runner's environment to override it.

The runner creates the `conformance` application user in `FREEPDB1` and applies
the [scenario schema](../../../../tools/database/runner/src/database_conformance/oracle.sql)
once, before measured processes start. Each session uses a fresh container
without reused volumes. The schema creates an empty table and a no-op stored
procedure. SQL*Plus exits with failure on SQL or operating-system errors.

Both JDBC instrumentation modes use the `ojdbc11` driver. The Java agent uses
`jdbc:oracle:thin:@//host:port/FREEPDB1`; JDBC library instrumentation uses
`jdbc:otel:oracle:thin:@//host:port/FREEPDB1`.

The [Oracle contract](../../../../tools/database/sql-test-client/contracts/oracle.yaml)
defines direct and prepared queries, a two-insert batch, and a stored-procedure
call. The direct query uses `CASE` to return a number rather than a SQL boolean,
and the procedure uses native SQL, `CALL conformance.noop()`.
Expected telemetry uses `db.system.name=oracle.db`.

The [pinned Oracle semantic conventions][oracle-semconv] define `db.namespace`
as `DB_UNIQUE_NAME`, which is `FREE` in this fixture, not the PDB or service name
`FREEPDB1`. Instrumentation may omit it if obtaining it requires an additional
network call. Java currently emits the lowercase service name `freepdb1`, which
does not satisfy this definition. The shared contract does not require
`db.namespace`; coverage still records the emitted attribute, but Weaver does
not check its Oracle-specific meaning. Recording this gap as a report-only
finding depends on [#384][contract-findings].

[oracle-semconv]: https://github.com/open-telemetry/semantic-conventions/blob/v1.45.0/docs/db/oracledb.md
[contract-findings]: https://github.com/open-telemetry/semantic-conventions-conformance/issues/384
