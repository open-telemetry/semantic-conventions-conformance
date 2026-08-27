plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":jdbc:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
