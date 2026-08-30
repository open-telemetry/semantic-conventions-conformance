plugins {
    id("otel-conformance.java-conventions")
    `java-library`
}

dependencies {
    implementation(project(":shared:mongodb:support"))
    // api: exposes com.mongodb.event.CommandListener, which MongoReactiveScenario's public
    // run(operation, commandListener) overload takes so a library launcher can register one.
    api(libs.mongodb.driver.reactivestreams)
    implementation(libs.reactivestreams)
}
