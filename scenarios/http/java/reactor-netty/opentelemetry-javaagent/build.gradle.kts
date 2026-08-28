plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":reactor-netty:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
