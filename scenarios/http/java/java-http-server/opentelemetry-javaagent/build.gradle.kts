plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":java-http-server:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
