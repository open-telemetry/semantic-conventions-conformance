plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.akka.actor)
    api(libs.akka.http)
    api(libs.akka.stream)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
