plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.opensearch.java)
    add("javaAgent", libs.opentelemetry.javaagent)
}
