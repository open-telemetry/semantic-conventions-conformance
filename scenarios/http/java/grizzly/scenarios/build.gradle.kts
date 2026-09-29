plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.grizzly.http.server)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
