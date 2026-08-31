# SQL database conformance test client

The workload every SQL database conformance scenario executes, shared so each
language measures the same operations.

Each file under [`contracts/`](contracts) owns one backend's named scenarios,
exact SQL, parameters, and procedure names.

Parameters use named `${parameter}` markers instead of a client library's bind
syntax. Each language helper renders those markers for its driver and binds the
listed values in order.

The database runner still supplies connection details and `DATABASE_BACKEND` at
runtime. These values depend on the container it started. Queries and parameters
are static contract data and do not pass through environment variables.

## Operation kinds

Each scenario has a stable name and one client operation kind:

| Kind | Adapter action |
| --- | --- |
| `query` | Run a direct query |
| `prepared_query` | Bind the listed parameters and run a prepared query |
| `batch` | Run the listed statements as one batch |
| `stored_procedure` | Call the named procedure |

Scenario names in each JSON file must match the same backend's telemetry
contract under `scenarios/database/contracts`. The SQL can vary independently by
backend. Operation kinds remain shared so each language adapter knows whether to
use a direct query, prepared query, batch, or stored procedure API. The scenario
process fails if the driver cannot execute an operation. Telemetry contracts
contain the assertions. Tests also require every matching conformance package to
wire each scenario name into its run command.

## Per language

Each language gets a small SQL helper that reads the selected backend file:

- [`java/`](java) provides `SqlContract`. The build copies
  `contracts/*.json` onto the classpath, and JDBC scenarios translate named
  parameters and stored procedures into JDBC calls.
