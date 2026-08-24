# Java conformance scenarios

Everything a JVM scenario shares: the build logic every Java build reuses, the
support every scenario needs whatever domain it measures, and the command that
builds and runs one.

```text
scenarios/<domain>/java/      a domain's Gradle build root — wrapper, settings, versions
tools/java/gradle-plugins/    the convention plugins, as an included build
tools/java/javaagent-test-extension/  exposes span scope names to the runner
tools/java/scenario-support/  what a scenario needs before any telemetry
tools/java/scenario-sdk/      the SDK a library-instrumentation scenario owns
tools/java/src/               `otel-conformance-java`, the launcher
tools/java/tests/             the launcher's tests
```

## A build root per domain

A domain's Java scenarios are one Gradle build, rooted at its own
`scenarios/<domain>/java` — today only
[`scenarios/http/java`](../../scenarios/http/java). `otel-conformance-java`
finds it by searching upwards from the scenario directory for
`settings.gradle.kts`, so a scenario file says nothing about how deep it is
nested. Within a build, projects are grouped by the library they instrument,
so `:armeria:scenarios` and `:armeria:opentelemetry-javaagent` sit beside the
Armeria scenario packages themselves.

What is not per domain is the build logic. [`gradle-plugins/`](gradle-plugins)
is an included build rather than a `buildSrc`, so a second domain's build root
reuses it instead of restating any of it:

- `otel-conformance.java-conventions` — toolchain, encoding, Spotless, JUnit,
  and Error Prone. Style is the formatter's job, so only Error Prone's own
  errors fail a build here: the patterns that are bugs rather than taste.
- `otel-conformance.scenario-launcher` — the `javaAgent` configuration and
  `prepareRuntime`, applied only by the projects that are scenario entry
  points. It also packages the test extension that copies each span's
  instrumentation scope name to `otel.scope.name`.

The projects under `tools/java` are shared the same way: a build root includes
them by directory, so both a `scenario-support` and a domain's own framework
projects sit in one project list.

Versions are pinned in a build root's `gradle/libs.versions.toml`. The Java
agent and the instrumentation BOM are one release published under two
coordinates, so a catalog is what keeps them from drifting apart and having the
agent scenarios measure a different instrumentation from the library ones.

## What a scenario shares

[`scenario-support/`](scenario-support) carries no OpenTelemetry dependency at
all, which is the point: an agent scenario's classpath must hold the agent's
instrumentation and nothing else, so what every scenario needs — the runner's
environment, and the driver's shutdown protocol — cannot live beside the SDK.

[`scenario-sdk/`](scenario-sdk) is the other half: SDK autoconfiguration, the
OTLP exporter, and shutdown, for scenarios measuring explicit library
instrumentation. A framework's launch project supplies only its own decorators.
Agent launch projects do not depend on it, so those jars never reach a runtime
that is meant to be measuring the agent.

## `otel-conformance-java`

Builds and runs a JVM conformance scenario, so no `conformance.yaml` restates
how Java is built. A scenario names its Gradle project and main class, and opts
into agent attachment when needed; nothing else about Java appears in the file.

```yaml
setup: otel-conformance-java prepare armeria:opentelemetry-javaagent

scenarios:
  server:
    run: otel-conformance-java run --agent armeria:opentelemetry-javaagent ArmeriaJavaagentServerScenario
```

The project is a Gradle path, so everything belonging to one instrumented
library can be grouped under it and two libraries can each have a `javaagent`
project without colliding.

The main class is unqualified because a scenario entry point sits in the
default package. Nothing imports one — it is reached only by name from the
command line — so a package would buy it no isolation and only lengthen the
line above. Everything reusable stays packaged.

`prepare` invokes the committed Gradle wrapper's `prepareRuntime`, which syncs
the resolved classpath and the Java agent into the build root's
`build/scenario-runtime/<project>`, with the path flattened to one directory
name. That is under the build root rather than under each project, so where a
Gradle project sits on disk is the build's business and not something the
launcher has to know.

`run` executes `java` directly rather than through Gradle, so the scenario
inherits the fresh OTLP endpoint the runner injected instead of whatever a
long-lived Gradle daemon started with.

`--agent` attaches the Java agent from the prepared runtime. It is a JVM launch
option, not an application mode, and is not passed to the scenario, so it goes
before the main class. Everything after the main class reaches the scenario
verbatim, including arguments that begin with `-`.
