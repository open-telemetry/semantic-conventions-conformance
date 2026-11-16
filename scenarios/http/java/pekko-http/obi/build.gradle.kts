plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":pekko-http:scenarios"))
}
