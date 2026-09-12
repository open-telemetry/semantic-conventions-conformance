plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(libs.redisson)
    implementation(project(":scenario-support"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
