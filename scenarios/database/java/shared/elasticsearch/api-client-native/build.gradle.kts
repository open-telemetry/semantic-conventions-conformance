plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(project(":scenario-sdk"))
    implementation(libs.elasticsearch.api.client)
}
