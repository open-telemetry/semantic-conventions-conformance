plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.couchbase3)
    add("javaAgent", libs.opentelemetry.javaagent)
}
