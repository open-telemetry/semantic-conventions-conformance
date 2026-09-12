plugins {
    id("otel-conformance.scenario-launcher")
    scala
}

dependencies {
    implementation(libs.rediscala)
    implementation(libs.scala.library)
    implementation(project(":scenario-support"))
    add("javaAgent", libs.opentelemetry.javaagent)
}
