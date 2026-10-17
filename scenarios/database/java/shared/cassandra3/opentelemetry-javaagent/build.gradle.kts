plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:cassandra3:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
