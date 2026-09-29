plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.restlet)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
