plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:hbase:hbase-client:scenarios"))
    implementation(project(":scenario-sdk"))
    runtimeOnly(libs.hbase.client)
}
