plugins {
    id("otel-conformance.scenario-launcher")
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.elasticsearch.transport.client)
    runtimeOnly(libs.elasticsearch.transport.netty4)
    runtimeOnly(libs.log4j.api)
    runtimeOnly(libs.log4j.core)
    add("javaAgent", libs.opentelemetry.javaagent)
}
