import org.gradle.api.tasks.Sync

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

val javaAgentExtension by configurations.creating {
    isCanBeConsumed = false
    isCanBeResolved = true
    isTransitive = false
}

dependencies {
    add(javaAgentExtension.name, project(":javaagent-test-extension"))
}

// Under the build root rather than under the project, so where a scenario
// project sits on disk is not something `otel-conformance-java` has to know.
// The whole project path, so two libraries can both have a `javaagent` project.
val runtimeName = project.path.removePrefix(":").replace(':', '-')
val runtimeDirectory = rootDir.resolve("build/scenario-runtime/$runtimeName")

tasks.register<Sync>("prepareRuntime") {
    dependsOn(tasks.jar)
    into(runtimeDirectory)

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
    from(javaAgentExtension) {
        into("agent")
        rename { "conformance-javaagent-extension.jar" }
    }
}
