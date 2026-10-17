plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:redis:lettuce:scenarios"))
    implementation(project(":scenario-support"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
