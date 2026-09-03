plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:hbase:scenarios"))
    runtimeOnly(libs.hbase1.client)
    add("javaAgent", libs.opentelemetry.javaagent)
}
