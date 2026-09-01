plugins {
    id("otel-conformance.java-conventions")
}

dependencies {
    implementation(libs.jackson.databind)
    implementation(libs.jackson.dataformat.yaml)
}

val contracts =
    fileTree("../contracts") {
        include("*.yaml")
    }
val contractIndex = layout.buildDirectory.file("generated-resources/contract-index.txt")
val generateContractIndex =
    tasks.register("generateContractIndex") {
        inputs.files(contracts)
        outputs.file(contractIndex)
        doLast {
            val index = contractIndex.get().asFile
            index.parentFile.mkdirs()
            index.writeText(
                contracts.files
                    .map { it.nameWithoutExtension }
                    .sorted()
                    .joinToString(separator = "\n", postfix = "\n"),
            )
        }
    }

tasks.processResources {
    from(contracts) {
        into("otel-sql-contracts")
    }
}

tasks.processTestResources {
    from(generateContractIndex) {
        into("otel-sql-contracts")
        rename { "index.txt" }
    }
}
