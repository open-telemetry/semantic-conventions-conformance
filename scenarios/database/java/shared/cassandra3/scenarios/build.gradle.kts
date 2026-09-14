plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    implementation(project(":scenario-support"))
    implementation(libs.cassandra.driver3)
}
