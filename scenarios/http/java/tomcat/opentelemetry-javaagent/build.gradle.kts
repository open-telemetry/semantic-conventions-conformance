plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":tomcat:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
