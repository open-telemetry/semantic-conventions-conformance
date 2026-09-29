/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.agent;

import io.opentelemetry.sdk.autoconfigure.spi.AutoConfigurationCustomizer;
import io.opentelemetry.sdk.autoconfigure.spi.AutoConfigurationCustomizerProvider;
import java.lang.management.ManagementFactory;
import javax.management.InstanceAlreadyExistsException;
import javax.management.MBeanServer;
import javax.management.ObjectName;
import javax.management.StandardMBean;

/** Exposes the agent-owned SDK's processors and readers to the scenario launcher. */
public final class AgentControlCustomizerProvider implements AutoConfigurationCustomizerProvider {
  public static final String OBJECT_NAME = "io.opentelemetry.conformance:type=AgentControl";

  private static final TelemetryFlusher FLUSHER = new TelemetryFlusher();

  public AgentControlCustomizerProvider() {
    register(FLUSHER);
  }

  @Override
  public void customize(AutoConfigurationCustomizer configuration) {
    configuration
        .addSpanProcessorCustomizer(
            (processor, properties) -> {
              FLUSHER.addTrace(processor::forceFlush);
              return processor;
            })
        .addLogRecordProcessorCustomizer(
            (processor, properties) -> {
              FLUSHER.addLog(processor::forceFlush);
              return processor;
            })
        .addMetricReaderCustomizer(
            (reader, properties) -> {
              FLUSHER.addMetric(reader::forceFlush);
              return reader;
            });
  }

  private static void register(TelemetryFlusher control) {
    try {
      MBeanServer server = ManagementFactory.getPlatformMBeanServer();
      server.registerMBean(
          new StandardMBean(control, AgentControlMBean.class), new ObjectName(OBJECT_NAME));
    } catch (InstanceAlreadyExistsException ignored) {
      // Auto-configuration may discover the provider more than once in one JVM.
    } catch (Exception exception) {
      throw new IllegalStateException(
          "could not register the conformance agent control", exception);
    }
  }
}
