plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:r2dbc:scenarios"))
    runtimeOnly(libs.r2dbc.postgresql)
    add("javaAgent", libs.opentelemetry.javaagent)
}
