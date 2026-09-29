/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.scenario;

import java.lang.management.ManagementFactory;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.Arrays;
import java.util.function.IntConsumer;
import javax.management.MBeanServer;
import javax.management.ObjectName;

/** Runs a scenario, then controls an agent-owned SDK before normal JVM shutdown. */
public final class ScenarioLauncher {
  private static final String AGENT_CONTROL_REQUIRED = "otel.conformance.agent.control.required";
  private static final String AGENT_CONTROL_NAME = "io.opentelemetry.conformance:type=AgentControl";
  private static final long FLUSH_TIMEOUT_MILLIS = 15_000;

  private ScenarioLauncher() {}

  public static void main(String[] arguments) throws Exception {
    run(arguments, System::exit);
  }

  static void run(String[] arguments, IntConsumer exit) throws Exception {
    if (arguments.length == 0) {
      throw new IllegalArgumentException("a scenario main class is required");
    }

    Throwable scenarioFailure = null;
    try {
      invokeScenario(arguments[0], Arrays.copyOfRange(arguments, 1, arguments.length));
    } catch (Throwable failure) {
      scenarioFailure = failure;
    }

    try {
      flushAgentSdk();
    } catch (Throwable flushFailure) {
      if (scenarioFailure == null) {
        scenarioFailure = flushFailure;
      } else {
        scenarioFailure.addSuppressed(flushFailure);
      }
    }

    boolean exitAfterFlush = ScenarioLifecycle.takeExitAfterFlushRequest();
    if (scenarioFailure != null) {
      if (exitAfterFlush) {
        scenarioFailure.printStackTrace(System.err);
        exit.accept(1);
        return;
      }
      rethrow(scenarioFailure);
    }

    if (exitAfterFlush) {
      exit.accept(0);
    }
  }

  private static void invokeScenario(String mainClass, String[] arguments) throws Throwable {
    try {
      Method main = Class.forName(mainClass).getMethod("main", String[].class);
      main.invoke(null, (Object) arguments);
    } catch (InvocationTargetException exception) {
      throw exception.getCause();
    }
  }

  private static void flushAgentSdk() throws Exception {
    if (!Boolean.getBoolean(AGENT_CONTROL_REQUIRED)) {
      return;
    }

    MBeanServer server = ManagementFactory.getPlatformMBeanServer();
    ObjectName control = new ObjectName(AGENT_CONTROL_NAME);
    if (!server.isRegistered(control)) {
      throw new IllegalStateException("the Java agent did not register its flush control");
    }

    long deadline = System.nanoTime() + FLUSH_TIMEOUT_MILLIS * 1_000_000;
    invoke(server, control, "flushTracesAndLogs", remainingMillis(deadline));
    invoke(server, control, "flushMetrics", remainingMillis(deadline));
  }

  private static void invoke(
      MBeanServer server, ObjectName control, String operation, long timeoutMillis)
      throws Exception {
    server.invoke(
        control, operation, new Object[] {timeoutMillis}, new String[] {long.class.getName()});
  }

  private static long remainingMillis(long deadline) {
    return Math.max(0, (deadline - System.nanoTime()) / 1_000_000);
  }

  private static void rethrow(Throwable failure) throws Exception {
    if (failure instanceof Error error) {
      throw error;
    }
    if (failure instanceof Exception exception) {
      throw exception;
    }
    throw new RuntimeException(failure);
  }
}
