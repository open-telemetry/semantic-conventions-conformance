plugins {
    id("otel-conformance.java-conventions")
    `java-library`
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
    api(libs.restlet1.api)
    api(libs.restlet1.engine)

    implementation(project(":http-test-client"))
    implementation(project(":scenario-support"))
}
