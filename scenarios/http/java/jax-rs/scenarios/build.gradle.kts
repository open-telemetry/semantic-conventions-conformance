plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.jersey.container.servlet)
    api(libs.tomcat.embed.core)

    runtimeOnly(libs.jersey.hk2)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
