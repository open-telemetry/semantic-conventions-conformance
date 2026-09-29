plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":okhttp:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
