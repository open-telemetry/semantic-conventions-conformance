plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.vertx.web)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
