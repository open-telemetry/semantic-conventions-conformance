plugins {
    id("otel-conformance.java-conventions")
    alias(libs.plugins.kotlin.jvm)
    `java-library`
}

dependencies {
    api(libs.ktor.client.core)
    api(libs.ktor.server.core)

    implementation(libs.ktor.client.cio)
    implementation(libs.ktor.server.netty)
    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
