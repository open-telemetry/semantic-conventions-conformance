plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":spring-webmvc:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
