plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    implementation(project(":shared:mongodb:support"))
    // api: exposes ServerAddress and CommandListener for the library launcher's listener factory.
    api(libs.mongodb.driver.async)
}

tasks.test {
    environment("DATABASE_HOST", "127.0.0.1")
    environment("DATABASE_PORT", "43210")
    environment("DATABASE_NAME", "conformance")
    environment("DATABASE_USER", "conformance")
    environment("DATABASE_PASSWORD", "conformance")
}
