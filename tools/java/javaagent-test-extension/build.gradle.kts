plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    compileOnly(platform(libs.opentelemetry.bom))
    compileOnly(libs.opentelemetry.javaagent.extension.api)
}
