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

include("akka-http:scenarios")
include("akka-http:opentelemetry-javaagent")
include("apache-httpasyncclient:scenarios")
include("apache-httpasyncclient:opentelemetry-javaagent")
include("apache-httpclient:scenarios")
include("apache-httpclient:opentelemetry-javaagent")
include("armeria:scenarios")
include("armeria:opentelemetry-javaagent")
include("armeria:opentelemetry-library")
include("async-http-client:scenarios")
include("async-http-client:opentelemetry-javaagent")
include("grizzly:scenarios")
include("grizzly:opentelemetry-javaagent")
include("helidon:scenarios")
include("helidon:opentelemetry-javaagent")
include("http-url-connection:scenarios")
include("http-url-connection:opentelemetry-javaagent")
include("java-http-client:scenarios")
include("java-http-client:opentelemetry-javaagent")
include("java-http-server:scenarios")
include("java-http-server:opentelemetry-javaagent")
include("jetty-httpclient:scenarios")
include("jetty-httpclient:opentelemetry-javaagent")
include("jodd-http:scenarios")
include("jodd-http:opentelemetry-javaagent")
include("netty:scenarios")
include("netty:opentelemetry-javaagent")
include("okhttp:scenarios")
include("okhttp:opentelemetry-javaagent")
include("pekko-http:scenarios")
include("pekko-http:opentelemetry-javaagent")
include("ratpack:scenarios")
include("ratpack:opentelemetry-javaagent")
include("reactor-netty:scenarios")
include("reactor-netty:opentelemetry-javaagent")
include("restlet:scenarios")
include("restlet:opentelemetry-javaagent")
include("servlet:scenarios")
include("servlet:opentelemetry-javaagent")
include("spring-webflux:scenarios")
include("spring-webflux:opentelemetry-javaagent")
include("tomcat:scenarios")
include("tomcat:opentelemetry-javaagent")
include("undertow:scenarios")
include("undertow:opentelemetry-javaagent")
include("vertx-http-client:scenarios")
include("vertx-http-client:opentelemetry-javaagent")

fun shared(name: String, directory: String) {
    include(name)
    project(":$name").projectDir = file(directory)
}

shared("scenario-support", "../../../tools/java/scenario-support")
shared("scenario-sdk", "../../../tools/java/scenario-sdk")
shared("http-test-client", "../../../tools/http/test-client/java")
