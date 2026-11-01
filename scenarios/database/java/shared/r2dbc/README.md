# R2DBC workload

PostgreSQL R2DBC packages run one reactive workload through the OpenTelemetry
Java agent or `opentelemetry-r2dbc-1.0` library instrumentation. The
`shared:r2dbc:scenarios` project owns the SQL and has no OpenTelemetry dependency.
Both launchers create the same PostgreSQL `ConnectionFactory`; the library
launcher wraps it with the instrumentation.

Each operation is a named scenario in
[`contracts/postgresql-r2dbc.yaml`](../../../contracts/postgresql-r2dbc.yaml):

| Scenario | Workload |
| --- | --- |
| `statement` | Run a plain `Statement` and verify `SELECT count(*) >= 0 FROM conformance.items` returns true. |
| `bind` | Bind `-1` to `$1` in `SELECT name FROM conformance.items WHERE id = $1` and verify no rows return. |
| `batch` | Execute two inserts through `Batch` and verify they update two rows. |
| `stored_procedure` | Execute `CALL conformance.noop()` through `Statement`. |
| `error` | Query `conformance.missing_items` and handle only PostgreSQL SQLSTATE `42P01`. |

The workload consumes results before closing the connection. The runner owns
the PostgreSQL container and schema initialization; each measured process only
connects and executes its selected operation. Connection pooling, transactions,
and cancellation are not covered.

## Contract and connection settings

The contract contains telemetry expectations only. Unlike the shared SQL
contracts, it does not inject an `action` object. Each package declares a run
command for every named operation. The separate contract records R2DBC-specific
namespace and bind-marker attributes and handled-error telemetry.

Packages construct `R2DBC_URL`, `R2DBC_USER`, and `R2DBC_PASSWORD` from the runner's
`DATABASE_HOST`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USER`, and
`DATABASE_PASSWORD`. Both modes opt into stable database semantic conventions.

## Running the packages

From the repository root, with Docker installed and running:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-javaagent
otel-conformance scenarios/database/java/postgresql/r2dbc/opentelemetry-library
```
