plugins {
    `kotlin-dsl`
}

repositories {
    gradlePluginPortal()
}

dependencies {
    implementation("com.diffplug.spotless:spotless-plugin-gradle:8.11.0")
    implementation("net.ltgt.gradle:gradle-errorprone-plugin:5.2.0")
}
