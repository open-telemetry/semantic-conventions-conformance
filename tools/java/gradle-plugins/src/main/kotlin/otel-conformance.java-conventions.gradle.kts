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
    compileOnly("org.jspecify:jspecify:1.0.0")
    testCompileOnly("org.jspecify:jspecify:1.0.0")

    errorprone("com.google.errorprone:error_prone_core:2.36.0")
    errorprone("com.uber.nullaway:nullaway:0.12.3")

    testImplementation(platform("org.junit:junit-bom:5.11.4"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
    options.errorprone {
        // Style is Spotless's job. What is worth failing a build over here is
        // the nullness contract, which no formatter can see.
        disableAllWarnings = true
        error("NullAway")
        option("NullAway:AnnotatedPackages", "io.opentelemetry.conformance")
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
