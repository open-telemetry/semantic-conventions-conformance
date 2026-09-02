# SQL database conformance test client

The workload every SQL database conformance scenario executes, shared so each
language measures the same operations.

Each file under [`contracts/`](contracts) owns one backend's ordered scenarios.
Every list entry keeps its description, SQL `action`, and telemetry `expect`
object together.

Parameters use named `${parameter}` markers instead of a client library's bind
syntax. Each language helper renders those markers for its driver and binds the
listed values in order.

The database runner supplies connection details and `DATABASE_BACKEND` at
runtime. These values depend on the container it started. The generic
conformance runner supplies the selected scenario's `action` as compact JSON in
`OTEL_CONFORMANCE_SCENARIO_ACTION`.

## Operation kinds

Each scenario has a human-readable description and one SQL action kind:

| Kind | Adapter action |
| --- | --- |
| `query` | Run a direct query |
| `prepared_query` | Bind the listed parameters and run a prepared query |
| `batch` | Run the listed statements as one batch |
| `stored_procedure` | Call the named procedure |

The SQL can vary independently by backend. Operation kinds remain shared so
each language adapter knows whether to use a direct query, prepared query,
batch, or stored procedure API. The language helper reads `action`; the
conformance runner reads `expect` using its generic `spans`, `metrics`, and
`events` matcher syntax. The scenario process fails if the driver cannot execute
the action. Tests also require every matching conformance package to reference
the same YAML contract and declare one `scenario_run` command.

The conformance runner creates a separate live-check for every list entry. The
same selected entry provides both the injected action and the telemetry
expectations, so language helpers do not load the full backend contract.
Descriptions are labels and may repeat.

## Per language

Each language gets a small SQL helper that parses the selected action:

- [`java/`](java) provides `SqlContract`, and JDBC scenarios translate named
  parameters and stored procedures into JDBC calls.
