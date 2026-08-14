pluginManagement {
    // An included build rather than a buildSrc: the toolchain, the formatter
    // and the launch wiring are shared with any other domain's Java build.
    includeBuild("../../../tools/java/gradle-plugins")
    repositories {
        gradlePluginPortal()
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "http-java-conformance"

// Listed rather than discovered by scanning, so the project list is readable
// here instead of being whichever directories happen to hold a build file.
// One group per instrumented library, matching where they sit on disk: an
// instrumentation's project sits with the packages that measure it.
include("armeria:scenarios")
include("armeria:opentelemetry-javaagent")
include("armeria:opentelemetry-library")

// Not this domain's to own: a gen-ai Java build includes the same projects
// from the same places.
fun shared(name: String, directory: String) {
    include(name)
    project(":$name").projectDir = file(directory)
}

shared("scenario-support", "../../../tools/java/scenario-support")
shared("scenario-sdk", "../../../tools/java/scenario-sdk")
shared("http-test-client", "../../../tools/http/test-client/java")
