plugins {
    id("otel-conformance.scenario-launcher")
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(27)
    }
}

dependencies {
    implementation(project(":helidon:scenarios"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
