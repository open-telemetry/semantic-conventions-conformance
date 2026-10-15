plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

// The launcher each vendor's library project runs; the vendor project adds
// its driver, so one resolution never credits a run with another's driver.
dependencies {
    implementation(project(":shared:jdbc:scenarios"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.jdbc)
}
