plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:cassandra:scenarios"))
    implementation(libs.cassandra.driver)
    add("javaAgent", libs.opentelemetry.javaagent)
}
