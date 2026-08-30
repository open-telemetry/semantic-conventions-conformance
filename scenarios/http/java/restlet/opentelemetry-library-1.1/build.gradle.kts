plugins {
    id("otel-conformance.scenario-launcher")
}

repositories {
    exclusiveContent {
        forRepository {
            maven("https://maven.restlet.talend.com/")
        }
        filter {
            includeGroup("org.restlet")
            includeGroup("com.noelios.restlet")
        }
    }
}

dependencies {
    implementation(project(":restlet:scenarios-1.1"))
    implementation(project(":scenario-sdk"))

    implementation(platform(libs.opentelemetry.instrumentation.bom.alpha))
    implementation(libs.opentelemetry.instrumentation.restlet1)
}
