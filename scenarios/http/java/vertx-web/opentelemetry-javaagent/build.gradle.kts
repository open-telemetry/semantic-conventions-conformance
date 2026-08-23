plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":vertx-web:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
