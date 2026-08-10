plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    implementation(project(":test-client"))
    implementation(platform("io.opentelemetry:opentelemetry-bom:1.64.0"))
    implementation(
        platform(
            "io.opentelemetry.instrumentation:" +
                "opentelemetry-instrumentation-bom-alpha:2.30.0-alpha",
        ),
    )

    implementation("com.linecorp.armeria:armeria:1.41.0")
    implementation("io.opentelemetry:opentelemetry-exporter-otlp")
    implementation("io.opentelemetry:opentelemetry-sdk-extension-autoconfigure")
    implementation("io.opentelemetry.instrumentation:opentelemetry-armeria-1.3")

    add("javaAgent", "io.opentelemetry.javaagent:opentelemetry-javaagent:2.30.0")
}
