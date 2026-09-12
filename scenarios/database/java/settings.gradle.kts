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

include("shared:mongodb:support")
include("shared:mongodb:sync:scenarios")
include("shared:mongodb:sync:opentelemetry-javaagent")
include("shared:mongodb:sync:opentelemetry-library")
include("shared:mongodb:async:scenarios")
include("shared:mongodb:async:opentelemetry-javaagent")
include("shared:mongodb:async:opentelemetry-library")
include("shared:mongodb:reactive:scenarios")
include("shared:mongodb:reactive:opentelemetry-javaagent")
include("shared:mongodb:reactive:opentelemetry-library")

fun shared(name: String, directory: String) {
    include(name)
    project(":$name").projectDir = file(directory)
}

shared("scenario-support", "../../../tools/java/scenario-support")
shared("scenario-sdk", "../../../tools/java/scenario-sdk")
