plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:jdbc:javaagent-launcher"))
    runtimeOnly(libs.mariadb)
    add("javaAgent", libs.opentelemetry.javaagent)
}

conformanceArtifacts {
    databaseDriver("org.mariadb.jdbc", "mariadb-java-client")
    instrumentationLibrary(
        "io.opentelemetry.javaagent",
        "opentelemetry-javaagent",
    )
}
