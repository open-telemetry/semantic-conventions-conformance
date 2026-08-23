plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.helidon.webserver)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
