plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.jodd.http)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
