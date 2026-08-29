plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.couchbase2)
    add("javaAgent", libs.opentelemetry.javaagent)
}
