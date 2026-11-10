plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":servlet:scenarios"))
    implementation(project(":scenario-support"))
}
