plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.opensearch.rest.v3)
    add("javaAgent", libs.opentelemetry.javaagent)
}
