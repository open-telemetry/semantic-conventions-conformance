plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(platform(libs.spring.boot.bom))
    api(libs.spring.boot.starter.web)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
