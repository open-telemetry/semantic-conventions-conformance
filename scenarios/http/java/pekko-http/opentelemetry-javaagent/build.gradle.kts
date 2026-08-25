plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":pekko-http:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
