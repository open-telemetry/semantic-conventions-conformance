plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

// The launcher each vendor's agent project runs; the vendor project adds its
// driver and the agent.
dependencies {
    implementation(project(":shared:jdbc:scenarios"))
}
