plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":tomcat:scenarios"))
}
