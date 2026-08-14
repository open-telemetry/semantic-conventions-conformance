plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    // Reading the contract, which is JSON because every language has to.
    // Not `api`: no Jackson type appears in this module's public API.
    implementation(libs.jackson.databind)
}

// The contract is shared with every other language, so it is read from where
// it lives rather than copied into this module's sources.
tasks.processResources {
    from("../contract.json") {
        rename { "otel-http-contract.json" }
    }
}
