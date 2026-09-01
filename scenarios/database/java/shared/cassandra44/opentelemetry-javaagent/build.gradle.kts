plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:cassandra4:scenarios"))
    implementation(libs.cassandra.driver44)
    add("javaAgent", libs.opentelemetry.javaagent)
}
