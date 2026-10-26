# SQL database conformance test client

The workload every SQL database conformance scenario executes, shared so each
language measures the same operations.

Each file under [`contracts/`](contracts) owns one backend's ordered scenarios.
Every list entry keeps its description, SQL `action`, and telemetry `expect`
object together.

Prepared queries use numbered `${1}`, `${2}` placeholders instead of a client
library's bind syntax. Parameter values are listed in the same order:

```yaml
action:
  kind: prepared_query
  sql: SELECT name FROM conformance.items WHERE id = ${1}
  parameters:
    - type: integer
      value: -1
```

Placeholders start at `${1}` and appear exactly once in ascending order, without
gaps. Their count must equal the number of parameters. The `${...}` syntax is
reserved for placeholders throughout prepared-query SQL; malformed or
unterminated placeholders are rejected. Parameters have no names.

Each language helper renders the placeholders for its driver, such as `?`, `$1`,
or `%s`, and binds the listed values in order. Question marks outside placeholders
are left unchanged, including those in SQL strings, comments, and operators.

The database runner supplies connection details for the container it started.
Each conformance package selects its backend's contract using `scenario_contract`.
The generic conformance runner supplies the selected scenario's `action` as
compact JSON in `OTEL_CONFORMANCE_SCENARIO_ACTION`.

## Operation kinds

Each scenario has a human-readable description and one SQL action kind:

| Kind | Adapter action |
| --- | --- |
| `query` | Run a direct query |
| `prepared_query` | Bind the listed parameters and run a prepared query |
| `batch` | Run the listed statements as one batch |
| `stored_procedure` | Execute the supplied call SQL through the stored procedure API |

Stored-procedure actions supply the complete backend-specific call SQL:

```yaml
action:
  kind: stored_procedure
  sql: CALL conformance.noop()
```

Adapters pass this SQL unchanged to their stored procedure API, such as JDBC's
`Connection.prepareCall`. The contract owns both the call SQL and its telemetry
expectations.

The SQL can vary independently by backend. Operation kinds remain shared so
each language adapter knows whether to use a direct query, prepared query,
batch, or stored procedure API. The language helper reads `action`; the
conformance runner reads `expect` using its generic `spans`, `metrics`, and
`events` matcher syntax. The scenario process fails if the driver cannot execute
the action. Each JDBC conformance package references its backend's YAML contract
and declares one `scenario_run` command. Other clients can reuse a SQL contract
without a matching JDBC package.

Adapters consume returned results without asserting row counts or values.
Execution and result-consumption errors fail the scenario. Batch adapters also
check that the driver reports a successful result for each submitted statement.

The conformance runner creates a separate live-check for every list entry. The
same selected entry provides both the injected action and the telemetry
expectations, so language helpers do not load the full backend contract.
Descriptions are labels and may repeat.

## Per language

Each language gets a small SQL helper that parses the selected action:

- [`java/`](java) provides `SqlContract`, and JDBC scenarios translate numbered
  placeholders and stored procedures into JDBC calls.
