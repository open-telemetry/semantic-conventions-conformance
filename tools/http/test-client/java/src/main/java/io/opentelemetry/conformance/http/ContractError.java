/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

/** A server answered something the contract does not describe. */
public final class ContractError extends RuntimeException {

  private static final long serialVersionUID = 1L;

  ContractError(String message) {
    super(message);
  }

  ContractError(String message, Throwable cause) {
    super(message, cause);
  }
}
