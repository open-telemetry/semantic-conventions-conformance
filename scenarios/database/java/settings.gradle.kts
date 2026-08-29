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

include("shared:jdbc:scenarios")
include("shared:jdbc:opentelemetry-javaagent")
include("shared:jdbc:opentelemetry-library")
include("opensearch:rest-1.0:opentelemetry-javaagent")
include("opensearch:rest-3.0:opentelemetry-javaagent")
include("opensearch:java-3.0:opentelemetry-javaagent")

fun shared(name: String, directory: String) {
    include(name)
    project(":$name").projectDir = file(directory)
}

shared("scenario-support", "../../../tools/java/scenario-support")
shared("scenario-sdk", "../../../tools/java/scenario-sdk")
