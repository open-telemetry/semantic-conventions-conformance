plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":jax-rs:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
