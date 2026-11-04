plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:mongodb:sync:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
