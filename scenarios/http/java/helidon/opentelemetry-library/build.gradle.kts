plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":helidon:scenarios"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.helidon)
}
