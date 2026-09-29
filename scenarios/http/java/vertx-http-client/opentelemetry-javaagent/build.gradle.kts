plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":vertx-http-client:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
