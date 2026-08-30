plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.tomcat9.embed.core)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
