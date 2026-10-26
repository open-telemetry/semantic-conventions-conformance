plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":shared:mongodb:reactive:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
