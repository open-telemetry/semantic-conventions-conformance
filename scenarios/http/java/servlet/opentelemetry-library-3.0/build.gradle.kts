plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":servlet:scenarios-3.0"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.servlet3)
}
