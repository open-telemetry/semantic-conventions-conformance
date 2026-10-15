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
include("shared:jdbc:javaagent-launcher")
include("shared:jdbc:library-launcher")
include("mariadb:jdbc:opentelemetry-javaagent")
include("mariadb:jdbc:opentelemetry-library")
include("postgresql:jdbc:opentelemetry-javaagent")
include("postgresql:jdbc:opentelemetry-library")

fun shared(name: String, directory: String) {
    include(name)
    project(":$name").projectDir = file(directory)
}

shared("scenario-support", "../../../tools/java/scenario-support")
shared("scenario-sdk", "../../../tools/java/scenario-sdk")
shared("agent-control", "../../../tools/java/agent-control")
