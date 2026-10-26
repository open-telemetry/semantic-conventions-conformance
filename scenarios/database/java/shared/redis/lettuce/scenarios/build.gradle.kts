plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    api(libs.lettuce)
}
