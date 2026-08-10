plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0"
}

rootProject.name = "http-java-conformance"

rootDir
    .listFiles()
    .orEmpty()
    .filter {
        it.name != "buildSrc" &&
            it.isDirectory &&
            it.resolve("build.gradle.kts").isFile
    }
    .sortedBy { it.name }
    .forEach { include(it.name) }

include("test-client")
project(":test-client").projectDir = file("../../../tools/http/test-client/java")
