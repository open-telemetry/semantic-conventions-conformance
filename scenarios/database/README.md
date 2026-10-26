# Database conformance scenarios

Database instrumentation is checked against the
[database semantic conventions][database] and recorded as committed coverage.
The [database runner](../../tools/database/runner/README.md) starts and prepares
the selected backend before measured processes run.

Scenario packages are organized by language and client. Reusable workloads and
launchers live in each language's `shared/` directory; instrumentation-specific
conformance configuration and coverage live in package directories. Language
helpers and backend-specific workload contracts live under
[`tools/database/`](../../tools/database/).

The shared SQL contract keeps each backend's action beside its generic telemetry
expectations. The action is passed to a language helper as JSON, which translates
it to the client API. See the
[SQL workload and contract conventions](../../tools/database/sql-test-client/README.md).
Redis uses named workloads and records client-specific telemetry in its
[shared workload guide](java/shared/redis/README.md).

## Running a package

Install the runner and Java support from the repository root, then run a
representative [JDBC Java-agent package](java/postgresql/jdbc/opentelemetry-javaagent):

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/postgresql/jdbc/opentelemetry-javaagent
```

Docker must be installed and running. A package run uses one backend container,
which is removed when the run ends. Stable database semantic conventions are
opted into by the scenarios because Java instrumentation otherwise emits legacy
database attributes during the migration period.

[database]: https://opentelemetry.io/docs/specs/semconv/db/
