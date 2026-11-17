plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":java-http-client:scenarios"))
}
