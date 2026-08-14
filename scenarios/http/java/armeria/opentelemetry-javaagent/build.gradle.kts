plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":armeria:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
