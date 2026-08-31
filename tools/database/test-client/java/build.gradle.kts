plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    implementation(libs.jackson.databind)
}

tasks.processResources {
    from("../contract.json") {
        rename { "otel-database-contract.json" }
    }
}
