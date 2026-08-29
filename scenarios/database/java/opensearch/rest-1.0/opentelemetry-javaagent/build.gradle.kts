plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.opensearch.rest.v1)
    add("javaAgent", libs.opentelemetry.javaagent)
}
