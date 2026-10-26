import groovy.json.JsonOutput
import org.gradle.api.tasks.Sync
import org.gradle.jvm.tasks.Jar

plugins {
    id("otel-conformance.java-conventions")
}

// Resolved on its own: an agent is attached to the JVM, never loaded by the
// application, so it must not reach the runtime classpath.
val javaAgent by configurations.creating {
    isCanBeConsumed = false
    isCanBeResolved = true
    isTransitive = false
}

// Under the build root rather than under the project, so where a scenario
// project sits on disk is not something `otel-conformance-java` has to know.
// The whole project path, so two libraries can both have a `javaagent` project.
val runtimeName = project.path.removePrefix(":").replace(':', '-')
val runtimeDirectory = rootDir.resolve("build/scenario-runtime/$runtimeName")

val javaLauncher = javaToolchains.launcherFor(java.toolchain)
val runtimeMetadata =
    tasks.register("writeJavaRuntimeMetadata") {
        val executable = javaLauncher.map { it.executablePath.asFile.absolutePath }
        val languageVersion = javaLauncher.map { it.metadata.languageVersion.asInt() }
        val output = layout.buildDirectory.file("generated/scenario-runtime/java-runtime.json")
        inputs.property("executable", executable)
        inputs.property("languageVersion", languageVersion)
        outputs.file(output)

        doLast {
            val file = output.get().asFile
            file.parentFile.mkdirs()
            file.writeText(
                JsonOutput.toJson(
                    mapOf(
                        "executable" to executable.get(),
                        "languageVersion" to languageVersion.get(),
                    ),
                ) + "\n",
            )
        }
    }

tasks.register<Sync>("prepareRuntime") {
    dependsOn(tasks.jar)
    into(runtimeDirectory)

    from(runtimeMetadata)
    from(tasks.jar) {
        into("lib")
    }
    from(configurations.runtimeClasspath) {
        into("lib")
    }
    from(javaAgent) {
        into("agent")
        rename { "opentelemetry-javaagent.jar" }
    }
    from(rootProject.project(":agent-control").tasks.named<Jar>("jar")) {
        into("agent")
        rename { "otel-conformance-agent-control.jar" }
    }
}
