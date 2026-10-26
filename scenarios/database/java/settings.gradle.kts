pluginManagement {
    includeBuild("../../../tools/java/gradle-plugins")
    repositories {
        gradlePluginPortal()
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "database-java-conformance"

fileTree(rootDir) {
    include("**/build.gradle", "**/build.gradle.kts")
    exclude("**/build/**", "**/.gradle/**", "**/out/**", "**/target/**")
}.files
    .sortedBy { it.relativeTo(rootDir).invariantSeparatorsPath }
    .forEach { buildFile ->
        val directory = buildFile.parentFile.relativeTo(rootDir).invariantSeparatorsPath
        if (directory.isNotEmpty()) {
            include(directory.replace("/", ":"))
        }
    }

fun shared(name: String, directory: String) {
    include(name)
    project(":$name").projectDir = file(directory)
}

shared("scenario-support", "../../../tools/java/scenario-support")
shared("scenario-sdk", "../../../tools/java/scenario-sdk")
shared("agent-control", "../../../tools/java/agent-control")
shared("sql-test-client", "../../../tools/database/sql-test-client/java")
