plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":apache-httpasyncclient:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
