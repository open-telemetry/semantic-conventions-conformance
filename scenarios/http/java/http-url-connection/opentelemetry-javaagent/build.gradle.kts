plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":http-url-connection:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
