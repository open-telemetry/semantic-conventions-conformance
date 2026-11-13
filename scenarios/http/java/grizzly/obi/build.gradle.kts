plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":grizzly:scenarios"))
    implementation(project(":scenario-support"))
}
