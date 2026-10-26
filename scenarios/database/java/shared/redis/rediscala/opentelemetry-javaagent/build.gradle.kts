plugins {
    id("otel-conformance.scenario-launcher")
    scala
}

dependencies {
    implementation(libs.rediscala)
    implementation(libs.scala.library)
    implementation(project(":scenario-support"))
    add("javaAgent", libs.opentelemetry.javaagent)
}

spotless {
    scala {
        scalafmt()
        licenseHeader(
            """
            /*
             * Copyright The OpenTelemetry Authors
             * SPDX-License-Identifier: Apache-2.0
             */
            """.trimIndent(),
            "(package|import|class|object|trait)",
        )
        target("src/**/*.scala")
    }
}

tasks.test {
    systemProperty(
        "scenario.classpath",
        sourceSets.main
            .get()
            .runtimeClasspath.asPath,
    )
}
