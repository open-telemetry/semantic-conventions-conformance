plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":grizzly:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
