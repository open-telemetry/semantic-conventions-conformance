plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    implementation(libs.jackson.databind)
    implementation(libs.jackson.dataformat.yaml)
}

// The contract is shared with every other language, so it is read from where
// it lives rather than copied into this module's sources.
tasks.processResources {
    from("../contract.yaml") {
        rename { "otel-http-contract.yaml" }
    }
}
