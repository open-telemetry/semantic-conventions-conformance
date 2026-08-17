plugins {
    `kotlin-dsl`
}

repositories {
    gradlePluginPortal()
}

dependencies {
    implementation("com.diffplug.spotless:spotless-plugin-gradle:8.10.0")
    implementation("net.ltgt.gradle:gradle-errorprone-plugin:4.4.0")
}
