plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    implementation(project(":scenario-support"))
    compileOnly(libs.hbase1.client)
}
