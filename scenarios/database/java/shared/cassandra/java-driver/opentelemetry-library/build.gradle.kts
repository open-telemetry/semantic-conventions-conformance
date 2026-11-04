plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:cassandra:java-driver:scenarios"))
    implementation(project(":scenario-sdk"))
    implementation(libs.cassandra.driver)

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.cassandra44)
}
