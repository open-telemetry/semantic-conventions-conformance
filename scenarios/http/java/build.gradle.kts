plugins {
    java
}

group = "io.opentelemetry.conformance"
version = "1.0"

repositories {
    mavenCentral()
}

val javaAgent by configurations.creating {
    isCanBeConsumed = false
    isCanBeResolved = true
    isTransitive = false
}

dependencies {
    implementation(platform("io.opentelemetry:opentelemetry-bom:1.64.0"))
    implementation(
        platform(
            "io.opentelemetry.instrumentation:" +
                "opentelemetry-instrumentation-bom-alpha:2.30.0-alpha",
        ),
    )

    implementation("com.linecorp.armeria:armeria:1.41.0")
    implementation("io.opentelemetry:opentelemetry-exporter-otlp")
    implementation("io.opentelemetry:opentelemetry-sdk-extension-autoconfigure")
    implementation("io.opentelemetry.instrumentation:opentelemetry-armeria-1.3")

    javaAgent("io.opentelemetry.javaagent:opentelemetry-javaagent:2.30.0")
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(17)
    }
}

sourceSets {
    main {
        java.srcDir("../../../tools/http/test-client/java/src/main/java")
    }
}

tasks.withType<JavaCompile>().configureEach {
    options.encoding = "UTF-8"
}

val prepareRuntime by tasks.registering(Sync::class) {
    dependsOn(tasks.jar)
    into(layout.projectDirectory.dir("runtime"))

    from(tasks.jar) {
        into("lib")
    }
    from(configurations.runtimeClasspath) {
        into("lib")
    }
    from(javaAgent) {
        into("agent")
        rename { "opentelemetry-javaagent.jar" }
    }
}
