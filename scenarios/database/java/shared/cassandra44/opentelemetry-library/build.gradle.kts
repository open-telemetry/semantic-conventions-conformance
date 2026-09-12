plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:cassandra4:scenarios"))
    implementation(project(":scenario-sdk"))
    implementation(libs.cassandra.driver44)

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.cassandra44)
}
