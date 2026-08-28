plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":netty:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
