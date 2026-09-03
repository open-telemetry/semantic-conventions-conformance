plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:jdbc:scenarios"))
    implementation(project(":scenario-sdk"))
    runtimeOnly(libs.mariadb)
    runtimeOnly(libs.oracle)
    runtimeOnly(libs.postgresql)

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.jdbc)
}
