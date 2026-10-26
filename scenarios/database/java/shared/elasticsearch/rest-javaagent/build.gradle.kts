plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.elasticsearch.rest.client)
    add("javaAgent", libs.opentelemetry.javaagent)
}
