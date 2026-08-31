# SQL database conformance test client

The workload every SQL database conformance scenario executes, shared so each
language measures the same operations and checks the same results.

[`contract.json`](contract.json) defines the operations once. SQL and procedure
names are keyed by backend because those belong to the database dialect.
Parameters use named `${parameter}` markers instead of a client library's bind
syntax. Each language helper renders those markers for its driver and binds the
listed values in order.

The database runner still supplies connection details and `DATABASE_BACKEND` at
runtime. These values depend on the container it started. Queries, parameters,
and expected results are static contract data and do not pass through
environment variables.

## Operations

Each operation has a stable name used by the conformance scenario:

| Operation | Contract action |
| --- | --- |
| `statement` | Run a direct query and check its single Boolean result |
| `prepared_statement` | Bind the listed parameters and check the row count |
| `batch` | Run the listed statements as one batch and check the success count |
| `stored_procedure` | Call the named procedure and check the result-set count |

A backend must provide the database-specific value for every operation. The
expected result remains shared because all backends implement the same logical
schema and workload. Other database families can define contracts with
operations that fit their data model instead of extending this SQL contract.

## Per language

Each language gets a small SQL helper that reads the shared file and exposes
the selected backend's workload:

- [`java/`](java) provides `SqlContract`. The build copies
  `contract.json` onto the classpath, and JDBC scenarios translate its named
  parameters and stored procedure into JDBC calls.
