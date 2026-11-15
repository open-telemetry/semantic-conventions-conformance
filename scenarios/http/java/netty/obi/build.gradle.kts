plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":netty:scenarios"))
}
