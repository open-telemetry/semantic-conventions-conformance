plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":armeria:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}

conformanceArtifacts {
    instrumentedLibrary("com.linecorp.armeria", "armeria")
    instrumentationLibrary(
        "io.opentelemetry.javaagent",
        "opentelemetry-javaagent",
    )
}
