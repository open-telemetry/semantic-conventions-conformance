plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":jetty-httpclient:scenarios"))
}
