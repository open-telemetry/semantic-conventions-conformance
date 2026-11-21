plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":spring-web:scenarios"))
}
