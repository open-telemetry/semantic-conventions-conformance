# MongoDB backend

Packages select `runner_config.backend: mongodb`. The runner starts a
digest-pinned MongoDB 7.0.45 container and supplies `DATABASE_HOST`, `DATABASE_PORT`,
`DATABASE_NAME`, `DATABASE_USER`, and `DATABASE_PASSWORD`. Drivers construct
their native connection settings from those fields and authenticate against
the supplied database.

MongoDB 7.0.45 is the temporary supported test server while available MongoDB 8.0
images reject Ubuntu 26.04's kernel version string. The vendor's
[Ubuntu kernel compatibility fix](https://jira.mongodb.org/browse/SERVER-131779)
is in MongoDB 8.0.37, but that official Docker image is not yet published.
The driver versions, instrumentation modes, workloads, and expectations do not
change with this server choice.

Readiness requires authorization to be enabled, so bootstrap waits for the
final daemon rather than the image's temporary initialization server. The
[packaged bootstrap](../../../../tools/database/runner/src/database_conformance/mongodb.js)
creates the scenario user and recreates `items` with four deterministic
documents. Each package run gets a fresh container, which is removed afterward.
The [workload guide](../shared/mongodb/README.md) describes the measured commands
and telemetry expectations.

Run packages from the repository root:

```sh
pip install -e tools/runner -e tools/database/runner -e tools/java
otel-conformance scenarios/database/java/mongodb/sync/opentelemetry-javaagent
otel-conformance scenarios/database/java/mongodb/sync/opentelemetry-library
otel-conformance scenarios/database/java/mongodb/reactive/opentelemetry-javaagent
otel-conformance scenarios/database/java/mongodb/reactive/opentelemetry-library
```

Docker must be installed and running. Packages opt into stable database semantic
conventions and classify MongoDB client spans as `db.mongodb.client`.
