plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:jdbc:scenarios"))
    runtimeOnly(libs.mariadb)
    runtimeOnly(libs.oracle)
    runtimeOnly(libs.postgresql)
    add("javaAgent", libs.opentelemetry.javaagent)
}
