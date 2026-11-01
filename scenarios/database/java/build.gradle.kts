// HBase's Hadoop dependencies need Java 21, including the shared code it loads.
configure(
    listOf(
        project(":shared:hbase:scenarios"),
        project(":hbase:native"),
        project(":scenario-support"),
        project(":scenario-sdk"),
    ),
) {
    plugins.withId("otel-conformance.java-conventions") {
        extensions.configure<JavaPluginExtension> {
            toolchain {
                languageVersion = JavaLanguageVersion.of(21)
            }
        }
    }
}
