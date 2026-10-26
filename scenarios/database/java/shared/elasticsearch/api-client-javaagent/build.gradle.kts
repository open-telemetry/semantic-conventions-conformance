plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.elasticsearch.api.client)
    implementation(libs.jackson.databind)
    add("javaAgent", libs.opentelemetry.javaagent)
}
