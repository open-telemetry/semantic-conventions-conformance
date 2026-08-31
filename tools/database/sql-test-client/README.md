# SQL database conformance test client

The workload every SQL database conformance scenario executes, shared so each
language measures the same operations and checks the same results.

Each file under [`contracts/`](contracts) owns one backend's named scenarios,
exact SQL, parameters, procedure names, and execution expectations.

Parameters use named `${parameter}` markers instead of a client library's bind
syntax. Each language helper renders those markers for its driver and binds the
listed values in order.

The database runner still supplies connection details and `DATABASE_BACKEND` at
runtime. These values depend on the container it started. Queries, parameters,
and expected results are static contract data and do not pass through
environment variables.

## Operation kinds

Each scenario has a stable name and one client operation kind:

| Kind | Adapter action |
| --- | --- |
| `query` | Run a direct query and check its single Boolean result |
| `prepared_query` | Bind the listed parameters and check the row count |
| `batch` | Run the listed statements as one batch and check the success count |
| `stored_procedure` | Call the named procedure and check the result-set count |

Scenario names in each JSON file must match the same backend's telemetry
contract under `scenarios/database/contracts`. The SQL and execution assertion
can vary independently by backend. Operation kinds remain shared so each
language adapter knows whether to use a direct query, prepared query, batch, or
stored procedure API. Tests also require every matching conformance package to
wire each scenario name into its run command.

## Per language

Each language gets a small SQL helper that reads the selected backend file:

- [`java/`](java) provides `SqlContract`. The build copies
  `contracts/*.json` onto the classpath, and JDBC scenarios translate named
  parameters and stored procedures into JDBC calls.
