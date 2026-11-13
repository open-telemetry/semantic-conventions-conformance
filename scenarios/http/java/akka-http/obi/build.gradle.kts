plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":akka-http:scenarios"))
    implementation(project(":scenario-support"))
}
