plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    implementation(project(":database-test-client"))
    implementation(project(":scenario-support"))
}
