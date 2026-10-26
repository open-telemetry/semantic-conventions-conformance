plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:redis:lettuce:scenarios"))
    implementation(project(":scenario-sdk"))
    implementation(project(":scenario-support"))
    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.lettuce)
}
