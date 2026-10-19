plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    implementation(libs.jackson.databind)
    implementation(project(":scenario-support"))
}
