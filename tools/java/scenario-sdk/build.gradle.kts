plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(platform(libs.opentelemetry.bom))
    api(libs.opentelemetry.api)

    implementation(project(":scenario-support"))
    implementation(libs.opentelemetry.exporter.otlp)
    implementation(libs.opentelemetry.sdk.extension.autoconfigure)
}
