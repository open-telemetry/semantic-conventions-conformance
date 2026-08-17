import net.ltgt.gradle.errorprone.errorprone
import org.gradle.api.tasks.compile.JavaCompile
import org.gradle.api.tasks.testing.Test
import org.gradle.jvm.toolchain.JavaLanguageVersion

plugins {
    java
    id("com.diffplug.spotless")
    id("net.ltgt.errorprone")
}

group = "io.opentelemetry.conformance"
version = "1.0"

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

dependencies {
    errorprone("com.google.errorprone:error_prone_core:2.50.0")

    testImplementation(platform("org.junit:junit-bom:6.1.3"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
    options.errorprone {
        // Style is Spotless's job, so only Error Prone's own errors — the
        // patterns that are bugs rather than taste — fail a build here.
        disableAllWarnings = true
    }
}

tasks.withType<Test>().configureEach {
    useJUnitPlatform()
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
