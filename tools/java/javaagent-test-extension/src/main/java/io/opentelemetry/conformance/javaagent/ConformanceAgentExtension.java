/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.javaagent;

import io.opentelemetry.sdk.autoconfigure.spi.AutoConfigurationCustomizer;
import io.opentelemetry.sdk.autoconfigure.spi.AutoConfigurationCustomizerProvider;

public final class ConformanceAgentExtension implements AutoConfigurationCustomizerProvider {
  @Override
  public void customize(AutoConfigurationCustomizer customizer) {
    customizer.addTracerProviderCustomizer(
        (builder, config) -> builder.addSpanProcessor(new ScopeAttributeSpanProcessor()));
  }
}
