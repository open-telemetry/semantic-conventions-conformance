import org.gradle.api.tasks.Sync
import org.gradle.api.tasks.compile.JavaCompile
import org.gradle.jvm.toolchain.JavaLanguageVersion

plugins {
    java
    id("com.diffplug.spotless")
}

group = "io.opentelemetry.conformance"
version = "1.0"

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(17)
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}

spotless {
    java {
        googleJavaFormat()
        licenseHeader(
            """
            /*
             * Copyright The OpenTelemetry Authors
             * SPDX-License-Identifier: Apache-2.0
             */
            """.trimIndent(),
            "(package|import|public)",
        )
        toggleOffOn()
        target("src/**/*.java")
    }
    kotlinGradle {
        ktlint()
    }
}

val javaAgent by configurations.creating {
    isCanBeConsumed = false
    isCanBeResolved = true
    isTransitive = false
}

tasks.register<Sync>("prepareRuntime") {
    dependsOn(tasks.jar)
    into(layout.projectDirectory.dir("runtime"))

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
}
