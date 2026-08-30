plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":apache-httpclient:scenarios-4.3"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.apache.httpclient43)
}
