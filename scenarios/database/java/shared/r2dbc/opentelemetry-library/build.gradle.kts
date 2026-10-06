plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:r2dbc:scenarios"))
    implementation(project(":scenario-sdk"))
    runtimeOnly(libs.r2dbc.postgresql)

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.r2dbc)
}
