plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":async-http-client:scenarios"))
}
