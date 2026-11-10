plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":spring-webflux:scenarios"))
    implementation(project(":scenario-support"))
}
