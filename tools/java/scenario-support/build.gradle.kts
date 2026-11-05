plugins {
    id("otel-conformance.java-conventions")
}

tasks.test {
    environment("OTEL_CONFORMANCE_TEST_EMPTY", "")
    environment("OTEL_CONFORMANCE_TEST_WHITESPACE", " ")
}
