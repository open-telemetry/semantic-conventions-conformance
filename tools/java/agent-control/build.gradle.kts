plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    compileOnly(platform(libs.opentelemetry.bom))
    compileOnly(libs.opentelemetry.sdk.extension.autoconfigure)

    testImplementation(platform(libs.opentelemetry.bom))
    testImplementation(libs.opentelemetry.sdk.extension.autoconfigure)
}
