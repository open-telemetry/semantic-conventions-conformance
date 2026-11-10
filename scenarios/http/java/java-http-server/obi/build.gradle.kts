plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":java-http-server:scenarios"))
    implementation(project(":scenario-support"))
}
