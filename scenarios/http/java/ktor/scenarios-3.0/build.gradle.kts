plugins {
    id("otel-conformance.java-conventions")
    alias(libs.plugins.kotlin.jvm)
    `java-library`
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    api(libs.ktor3.client.core)
    api(libs.ktor3.server.core)

    implementation(libs.ktor3.client.cio)
    implementation(libs.ktor3.server.netty)
    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
