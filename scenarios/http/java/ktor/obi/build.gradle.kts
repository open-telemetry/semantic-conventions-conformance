plugins {
    id("otel-conformance.scenario-launcher")
    alias(libs.plugins.kotlin.jvm)
}

dependencies {
    implementation(project(":ktor:scenarios"))
}
