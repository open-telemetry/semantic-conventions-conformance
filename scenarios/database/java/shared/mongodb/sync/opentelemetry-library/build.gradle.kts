plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:mongodb:sync:scenarios"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.mongo)
}
