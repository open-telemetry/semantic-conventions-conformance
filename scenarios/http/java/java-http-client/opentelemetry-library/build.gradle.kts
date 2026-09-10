plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":java-http-client:scenarios"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.java.http.client)
}
