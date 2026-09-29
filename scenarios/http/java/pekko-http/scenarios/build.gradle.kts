plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.pekko.actor)
    api(libs.pekko.http)
    api(libs.pekko.stream)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
