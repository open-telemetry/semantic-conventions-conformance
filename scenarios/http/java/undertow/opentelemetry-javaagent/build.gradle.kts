plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":undertow:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
