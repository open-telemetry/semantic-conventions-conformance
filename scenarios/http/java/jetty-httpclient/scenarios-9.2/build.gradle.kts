plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.jetty.client9)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
