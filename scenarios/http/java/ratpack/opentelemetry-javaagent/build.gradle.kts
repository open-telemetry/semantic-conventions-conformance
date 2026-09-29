plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":ratpack:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
