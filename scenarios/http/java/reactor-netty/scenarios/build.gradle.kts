plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.reactor.netty.http)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
