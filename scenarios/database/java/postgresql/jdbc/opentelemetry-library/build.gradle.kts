plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:jdbc:library-launcher"))
    runtimeOnly(libs.postgresql)
}

conformanceArtifacts {
    databaseDriver("org.postgresql", "postgresql")
    instrumentationLibrary(
        "io.opentelemetry.instrumentation",
        "opentelemetry-jdbc",
    )
}
