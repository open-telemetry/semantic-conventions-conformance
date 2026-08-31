plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    implementation(libs.jackson.databind)
    implementation(libs.jackson.dataformat.yaml)
}

tasks.processResources {
    from("../contracts") {
        into("otel-sql-contracts")
    }
}
