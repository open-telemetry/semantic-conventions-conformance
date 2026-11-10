plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":armeria:scenarios"))
    implementation(project(":scenario-support"))
}
