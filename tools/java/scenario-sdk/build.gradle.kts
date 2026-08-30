plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(platform(libs.opentelemetry.bom))
    api(libs.opentelemetry.api)

    implementation(project(":scenario-support"))
    implementation(libs.opentelemetry.exporter.otlp) {
        exclude(group = "io.opentelemetry", module = "opentelemetry-exporter-sender-okhttp")
    }
    runtimeOnly(libs.opentelemetry.exporter.sender.grpc.managed.channel)
    runtimeOnly(libs.grpc.netty.shaded)
    implementation(libs.opentelemetry.sdk.extension.autoconfigure)
}
