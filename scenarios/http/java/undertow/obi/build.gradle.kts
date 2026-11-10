plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":undertow:scenarios"))
    implementation(project(":scenario-support"))
}
