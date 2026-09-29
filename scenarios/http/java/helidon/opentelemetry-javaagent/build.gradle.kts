plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":helidon:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
