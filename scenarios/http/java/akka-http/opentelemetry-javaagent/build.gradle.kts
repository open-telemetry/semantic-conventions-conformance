plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":akka-http:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
