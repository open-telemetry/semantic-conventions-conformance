plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:hbase:scenarios"))
    implementation(project(":scenario-sdk"))
    runtimeOnly(libs.hbase.client)
}
