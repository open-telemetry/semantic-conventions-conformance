plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.netty.codec.http)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
