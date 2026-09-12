/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.agent;

/** Operations the scenario launcher invokes before the agent-owned SDK shuts down. */
public interface AgentControlMBean {
  void flushTracesAndLogs(long timeoutMillis);

  void flushMetrics(long timeoutMillis);
}
