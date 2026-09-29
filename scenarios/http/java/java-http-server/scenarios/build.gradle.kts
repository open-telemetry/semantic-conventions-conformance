plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
