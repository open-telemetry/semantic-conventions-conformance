plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.ratpack.core)
    api(libs.ratpack.test)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
