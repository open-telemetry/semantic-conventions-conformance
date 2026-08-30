plugins {
    id("otel-conformance.java-conventions")
    alias(libs.plugins.kotlin.jvm)
    `java-library`
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    api(libs.ktor1.server.core)

    implementation(libs.ktor1.server.netty)
    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
