/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */

import java.nio.file.Path
import kotlin.io.path.createDirectories
import kotlin.io.path.readText
import kotlin.io.path.writeText
import org.gradle.testkit.runner.GradleRunner
import org.gradle.testkit.runner.TaskOutcome
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir

class ScenarioLauncherPluginTest {
    @TempDir lateinit var projectDirectory: Path

    @Test
    fun `writes direct and BOM-managed resolved versions in stable order`() {
        fixture(
            """
            dependencies {
                implementation(platform("io.opentelemetry.instrumentation:opentelemetry-instrumentation-bom-alpha:2.31.1-alpha"))
                implementation("io.opentelemetry.instrumentation:opentelemetry-armeria-1.3")
                implementation("com.linecorp.armeria:armeria:1.41.1")
            }

            conformanceArtifacts {
                instrumentedLibrary("com.linecorp.armeria", "armeria")
                instrumentationLibrary("io.opentelemetry.instrumentation", "opentelemetry-armeria-1.3")
            }
            """,
        )

        val result = run("prepareRuntime")

        assertEquals(TaskOutcome.SUCCESS, result.task(":prepareRuntime")?.outcome)
        assertEquals(
            """
            {
              "schema_version": 1,
              "generated_by": "otel-conformance-java prepare",
              "artifacts": [
                {
                  "role": "instrumentation_library",
                  "ecosystem": "maven",
                  "coordinate": "io.opentelemetry.instrumentation:opentelemetry-armeria-1.3",
                  "version": "2.31.1-alpha"
                },
                {
                  "role": "instrumented_library",
                  "ecosystem": "maven",
                  "coordinate": "com.linecorp.armeria:armeria",
                  "version": "1.41.1"
                }
              ]
            }
            """.trimIndent() + "\n",
            artifactsFile().readText(),
        )
        assertEquals(
            artifactsFile().readText(),
            projectDirectory
                .resolve("build/scenario-runtime/artifacts.json")
                .readText(),
        )
    }

    @Test
    fun `resolves a non-transitive java agent configuration`() {
        fixture(
            """
            dependencies {
                implementation("com.linecorp.armeria:armeria:1.41.1")
                add("javaAgent", "io.opentelemetry.javaagent:opentelemetry-javaagent:2.31.1")
            }

            conformanceArtifacts {
                instrumentedLibrary("com.linecorp.armeria", "armeria")
                instrumentationLibrary("io.opentelemetry.javaagent", "opentelemetry-javaagent")
            }
            """,
        )

        run("writeConformanceArtifacts")

        assertTrue(
            artifactsFile()
                .readText()
                .contains(
                    "\"coordinate\": \"io.opentelemetry.javaagent:opentelemetry-javaagent\",\n" +
                        "      \"version\": \"2.31.1\"",
                ),
        )
    }

    @Test
    fun `missing selection identifies project role and coordinate`() {
        fixture(
            """
            dependencies {
                implementation("com.linecorp.armeria:armeria:1.41.1")
            }

            conformanceArtifacts {
                instrumentedLibrary("com.linecorp.armeria", "missing")
            }
            """,
        )

        val failure = runAndFail("writeConformanceArtifacts")

        assertTrue(
            failure.output.contains(
                "Project : resolved 0 versions for instrumented_library " +
                    "com.linecorp.armeria:missing",
            ),
        )
    }

    @Test
    fun `ambiguous selection identifies project role and coordinate`() {
        fixture(
            """
            dependencies {
                implementation("com.linecorp.armeria:armeria:1.41.1")
                add("javaAgent", "com.linecorp.armeria:armeria:1.40.0")
            }

            conformanceArtifacts {
                instrumentationLibrary("com.linecorp.armeria", "armeria")
            }
            """,
        )

        val failure = runAndFail("writeConformanceArtifacts")

        assertTrue(
            failure.output.contains(
                "Project : resolved 2 versions for instrumentation_library " +
                    "com.linecorp.armeria:armeria",
            ),
        )
    }

    private fun fixture(body: String) {
        projectDirectory.resolve("settings.gradle.kts").writeText(
            """
            rootProject.name = "test-scenario"
            include("agent-control")
            """.trimIndent(),
        )
        val agentControl = projectDirectory.resolve("agent-control")
        agentControl.createDirectories()
        agentControl.resolve("build.gradle.kts").writeText("plugins { java }\n")
        projectDirectory.resolve("build.gradle.kts").writeText(
            """
            plugins {
                id("otel-conformance.scenario-launcher")
            }

            repositories {
                mavenCentral()
            }

            $body
            """.trimIndent(),
        )
    }

    private fun artifactsFile(): Path =
        projectDirectory.resolve("build/generated/conformance/artifacts.json")

    private fun run(vararg arguments: String) =
        GradleRunner
            .create()
            .withProjectDir(projectDirectory.toFile())
            .withPluginClasspath()
            .withArguments(*arguments, "--stacktrace")
            .build()

    private fun runAndFail(vararg arguments: String) =
        GradleRunner
            .create()
            .withProjectDir(projectDirectory.toFile())
            .withPluginClasspath()
            .withArguments(*arguments, "--stacktrace")
            .buildAndFail()
}
