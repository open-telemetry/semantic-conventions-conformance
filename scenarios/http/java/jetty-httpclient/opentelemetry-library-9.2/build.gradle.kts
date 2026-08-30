plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":jetty-httpclient:scenarios-9.2"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.jetty.httpclient9)
}
