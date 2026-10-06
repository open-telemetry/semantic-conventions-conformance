plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:jdbc:library-launcher"))
    runtimeOnly(libs.mariadb)
}

conformanceArtifacts {
    databaseDriver("org.mariadb.jdbc", "mariadb-java-client")
    instrumentationLibrary(
        "io.opentelemetry.instrumentation",
        "opentelemetry-jdbc",
    )
}
