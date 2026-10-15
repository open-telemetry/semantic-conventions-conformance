plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:jdbc:javaagent-launcher"))
    runtimeOnly(libs.postgresql)
    add("javaAgent", libs.opentelemetry.javaagent)
}

conformanceArtifacts {
    databaseDriver("org.postgresql", "postgresql")
    instrumentationLibrary(
        "io.opentelemetry.javaagent",
        "opentelemetry-javaagent",
    )
}
