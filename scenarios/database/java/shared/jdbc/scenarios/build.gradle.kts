plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    implementation(project(":sql-test-client"))
    implementation(project(":scenario-support"))
}
