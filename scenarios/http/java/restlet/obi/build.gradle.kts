plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":restlet:scenarios"))
}
