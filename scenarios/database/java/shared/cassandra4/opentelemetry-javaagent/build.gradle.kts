plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:cassandra4:scenarios"))
    implementation(libs.cassandra.driver43)
    add("javaAgent", libs.opentelemetry.javaagent)
}
