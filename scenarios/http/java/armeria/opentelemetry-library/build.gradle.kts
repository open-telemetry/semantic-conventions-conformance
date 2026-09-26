plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":armeria:scenarios"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.armeria)
}

conformanceArtifacts {
    instrumentedLibrary("com.linecorp.armeria", "armeria")
    instrumentationLibrary(
        "io.opentelemetry.instrumentation",
        "opentelemetry-armeria-1.3",
    )
}
