plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(libs.jedis)
    implementation(project(":scenario-support"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
