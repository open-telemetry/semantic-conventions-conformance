/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.lang.management.ManagementFactory;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import javax.management.MBeanServer;
import javax.management.ObjectName;
import javax.management.StandardMBean;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class ScenarioLauncherTest {
  @TempDir Path directory;

  private static final String CONTROL_NAME = "io.opentelemetry.conformance:type=AgentControl";
  private static final String CONTROL_REQUIRED = "otel.conformance.agent.control.required";
  private static final List<String> EVENTS = new ArrayList<>();

  @Test
  void runsTheScenarioThenFlushesAgentSignalsInOrder() throws Exception {
    MBeanServer server = ManagementFactory.getPlatformMBeanServer();
    ObjectName name = new ObjectName(CONTROL_NAME);
    TestControl control = new TestControl();
    server.registerMBean(new StandardMBean(control, TestControlMBean.class), name);
    System.setProperty(CONTROL_REQUIRED, "true");
    EVENTS.clear();

    try {
      ScenarioLauncher.main(new String[] {TestScenario.class.getName()});
    } finally {
      System.clearProperty(CONTROL_REQUIRED);
      server.unregisterMBean(name);
    }

    assertEquals(List.of("scenario", "trace and log", "metric"), EVENTS);
  }

  @Test
  void exitsOnlyAfterFlushingAgentSignals() throws Exception {
    MBeanServer server = ManagementFactory.getPlatformMBeanServer();
    ObjectName name = new ObjectName(CONTROL_NAME);
    TestControl control = new TestControl();
    server.registerMBean(new StandardMBean(control, TestControlMBean.class), name);
    System.setProperty(CONTROL_REQUIRED, "true");
    EVENTS.clear();

    try {
      ScenarioLauncher.run(
          new String[] {ExitScenario.class.getName()}, status -> EVENTS.add("exit " + status));
    } finally {
      System.clearProperty(CONTROL_REQUIRED);
      server.unregisterMBean(name);
    }

    assertEquals(List.of("scenario", "trace and log", "metric", "exit 0"), EVENTS);
  }

  @Test
  void runsTheScenarioOnceTheGateIsReleased() throws Exception {
    Path gate = Files.createTempFile(directory, "gate", "");
    Files.write(gate, new byte[] {'1'});
    EVENTS.clear();

    ScenarioLauncher.run(
        new String[] {TestScenario.class.getName()},
        status -> EVENTS.add("exit " + status),
        gate.toString());

    assertEquals(List.of("scenario"), EVENTS);
  }

  @Test
  void doesNotRunTheScenarioPastAClosedGate() throws Exception {
    Path gate = Files.createTempFile(directory, "gate", "");
    EVENTS.clear();

    IllegalStateException error =
        assertThrows(
            IllegalStateException.class,
            () ->
                ScenarioLauncher.run(
                    new String[] {TestScenario.class.getName()},
                    status -> EVENTS.add("exit " + status),
                    gate.toString()));

    assertEquals("the launcher closed the gate without releasing it", error.getMessage());
    assertEquals(List.of(), EVENTS);
  }

  public interface TestControlMBean {
    void flushTracesAndLogs(long timeoutMillis);

    void flushMetrics(long timeoutMillis);
  }

  public static final class TestControl implements TestControlMBean {
    @Override
    public void flushTracesAndLogs(long timeoutMillis) {
      EVENTS.add("trace and log");
    }

    @Override
    public void flushMetrics(long timeoutMillis) {
      EVENTS.add("metric");
    }
  }

  public static final class TestScenario {
    private TestScenario() {}

    public static void main(String[] arguments) {
      EVENTS.add("scenario");
    }
  }

  public static final class ExitScenario {
    private ExitScenario() {}

    public static void main(String[] arguments) {
      EVENTS.add("scenario");
      ScenarioLifecycle.exitAfterFlush();
    }
  }
}
