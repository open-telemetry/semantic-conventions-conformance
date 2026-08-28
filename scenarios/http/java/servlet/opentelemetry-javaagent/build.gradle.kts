plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":servlet:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
