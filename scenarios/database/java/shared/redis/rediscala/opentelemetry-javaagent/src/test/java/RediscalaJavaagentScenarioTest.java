/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class RediscalaJavaagentScenarioTest {
  @TempDir Path directory;

  @Test
  void exitsWhenHostIsMissing() throws Exception {
    assertFailsPromptly(
        Map.of("DATABASE_PORT", "6379"),
        "set_get",
        "required environment variable is missing: DATABASE_HOST");
  }

  @Test
  void exitsWhenPortIsMissing() throws Exception {
    assertFailsPromptly(
        Map.of("DATABASE_HOST", "127.0.0.1"),
        "set_get",
        "required environment variable is missing: DATABASE_PORT");
  }

  @Test
  void exitsWhenPortIsInvalid() throws Exception {
    assertFailsPromptly(
        Map.of("DATABASE_HOST", "127.0.0.1", "DATABASE_PORT", "not-a-port"),
        "set_get",
        "NumberFormatException");
  }

  @Test
  void exitsWhenDatabaseIsInvalid() throws Exception {
    assertFailsPromptly(
        Map.of(
            "DATABASE_HOST",
            "127.0.0.1",
            "DATABASE_PORT",
            "6379",
            "DATABASE_NAME",
            "not-a-database"),
        "set_get",
        "NumberFormatException");
  }

  @Test
  void exitsWhenDatabaseIsNegative() throws Exception {
    assertFailsPromptly(
        Map.of("DATABASE_HOST", "127.0.0.1", "DATABASE_PORT", "6379", "DATABASE_NAME", "-1"),
        "set_get",
        "DATABASE_NAME must be a non-negative Redis database index");
  }

  @Test
  void exitsWhenOperationIsUnknown() throws Exception {
    assertFailsPromptly(
        Map.of("DATABASE_HOST", "127.0.0.1", "DATABASE_PORT", "6379"),
        "unknown",
        "unknown Rediscala operation: unknown");
  }

  private void assertFailsPromptly(
      Map<String, String> environment, String operation, String expectedError) throws Exception {
    Path output = directory.resolve("scenario.log");
    ProcessBuilder builder =
        new ProcessBuilder(
                ProcessHandle.current().info().command().orElseThrow(),
                "-cp",
                System.getProperty("scenario.classpath"),
                "RediscalaJavaagentScenario",
                operation)
            .redirectErrorStream(true)
            .redirectOutput(output.toFile());
    builder.environment().remove("DATABASE_HOST");
    builder.environment().remove("DATABASE_PORT");
    builder.environment().put("DATABASE_NAME", "0");
    builder.environment().put("DATABASE_USER", "default");
    builder.environment().put("DATABASE_PASSWORD", "");
    builder.environment().putAll(environment);

    Process process = builder.start();
    try {
      assertTrue(process.waitFor(15, TimeUnit.SECONDS), "scenario did not exit after failing");
      assertNotEquals(0, process.exitValue());
      assertTrue(Files.readString(output).contains(expectedError), Files.readString(output));
    } finally {
      if (process.isAlive()) {
        process.destroyForcibly().waitFor(5, TimeUnit.SECONDS);
      }
    }
  }
}
