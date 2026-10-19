// HBase's Hadoop dependencies need Java 21, including the shared code it loads.
configure(
    listOf(
        project(":shared:hbase:scenarios"),
        project(":hbase:hbase-1:opentelemetry-javaagent"),
        project(":hbase:hbase-2:opentelemetry-javaagent"),
        project(":scenario-support"),
        project(":agent-control"),
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
