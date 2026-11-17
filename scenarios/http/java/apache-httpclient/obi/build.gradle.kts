plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":apache-httpclient:scenarios"))
}
