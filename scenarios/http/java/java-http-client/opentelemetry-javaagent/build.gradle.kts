plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":java-http-client:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
