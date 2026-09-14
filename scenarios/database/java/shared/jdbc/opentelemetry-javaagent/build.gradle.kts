plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:jdbc:scenarios"))
    runtimeOnly(libs.mariadb)
    runtimeOnly(libs.mssql)
    runtimeOnly(libs.postgresql)
    add("javaAgent", libs.opentelemetry.javaagent)
}
