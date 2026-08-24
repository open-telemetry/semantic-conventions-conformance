/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.javaagent;

import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.context.Context;
import io.opentelemetry.sdk.common.CompletableResultCode;
import io.opentelemetry.sdk.trace.ReadWriteSpan;
import io.opentelemetry.sdk.trace.ReadableSpan;
import io.opentelemetry.sdk.trace.SpanProcessor;

final class ScopeAttributeSpanProcessor implements SpanProcessor {
  private static final AttributeKey<String> SCOPE_NAME = AttributeKey.stringKey("otel.scope.name");

  @Override
  public void onStart(Context parentContext, ReadWriteSpan span) {
    span.setAttribute(SCOPE_NAME, span.getInstrumentationScopeInfo().getName());
  }

  @Override
  public boolean isStartRequired() {
    return true;
  }

  @Override
  public void onEnd(ReadableSpan span) {}

  @Override
  public boolean isEndRequired() {
    return false;
  }

  @Override
  public CompletableResultCode shutdown() {
    return CompletableResultCode.ofSuccess();
  }

  @Override
  public CompletableResultCode forceFlush() {
    return CompletableResultCode.ofSuccess();
  }
}
