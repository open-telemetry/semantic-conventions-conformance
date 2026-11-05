plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(27)
    }
}

dependencies {
    api(libs.helidon.webserver)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
