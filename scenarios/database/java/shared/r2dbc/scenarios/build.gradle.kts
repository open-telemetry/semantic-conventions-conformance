plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.r2dbc.spi)
    implementation(project(":scenario-support"))
    implementation(libs.reactor.core)
}
