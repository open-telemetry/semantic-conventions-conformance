plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.httpclient4)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
