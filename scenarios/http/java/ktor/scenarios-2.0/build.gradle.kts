plugins {
    id("otel-conformance.java-conventions")
    alias(libs.plugins.kotlin.jvm)
    `java-library`
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    api(libs.ktor2.client.core)
    api(libs.ktor2.server.core)

    implementation(libs.ktor2.client.cio)
    implementation(libs.ktor2.server.netty)
    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
