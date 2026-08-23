pluginManagement {
    includeBuild("../../../tools/java/gradle-plugins")
    repositories {
        gradlePluginPortal()
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "http-java-conformance"

// One group per instrumented library: its `scenarios` project is what the
// exchanges are driven through, and a project per instrumentation is what
// turns that instrumentation on.
fun library(name: String, vararg instrumentations: String) {
    include("$name:scenarios")
    instrumentations.forEach { include("$name:$it") }
}

library("akka-http", "opentelemetry-javaagent")
library("apache-httpasyncclient", "opentelemetry-javaagent")
library("apache-httpclient", "opentelemetry-javaagent")
library("armeria", "opentelemetry-javaagent", "opentelemetry-library")
library("async-http-client", "opentelemetry-javaagent")
library("grizzly", "opentelemetry-javaagent")
library("helidon", "opentelemetry-javaagent")
library("http-url-connection", "opentelemetry-javaagent")
library("java-http-client", "opentelemetry-javaagent")
library("java-http-server", "opentelemetry-javaagent")
library("jax-rs", "opentelemetry-javaagent")
library("jetty-httpclient", "opentelemetry-javaagent")
library("jodd-http", "opentelemetry-javaagent")
library("netty", "opentelemetry-javaagent")
library("okhttp", "opentelemetry-javaagent")
library("pekko-http", "opentelemetry-javaagent")
library("ratpack", "opentelemetry-javaagent")
library("reactor-netty", "opentelemetry-javaagent")
library("restlet", "opentelemetry-javaagent")
library("servlet", "opentelemetry-javaagent")
library("spring-webflux", "opentelemetry-javaagent")
library("spring-webmvc", "opentelemetry-javaagent")
library("tomcat", "opentelemetry-javaagent")
library("undertow", "opentelemetry-javaagent")
library("vertx-http-client", "opentelemetry-javaagent")
library("vertx-web", "opentelemetry-javaagent")

fun shared(name: String, directory: String) {
    include(name)
    project(":$name").projectDir = file(directory)
}

shared("scenario-support", "../../../tools/java/scenario-support")
shared("scenario-sdk", "../../../tools/java/scenario-sdk")
shared("http-test-client", "../../../tools/http/test-client/java")
