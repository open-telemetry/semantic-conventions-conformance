/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.http;

import io.opentelemetry.conformance.http.HttpContract.Exchange;
import java.util.List;

final class TestActions {
  static final String JSON =
      """
      [
        {"request":{"method":"GET","path":"/health"},"response":{"status":200,"body":"{\\"ok\\": true}"}},
        {"request":{"method":"GET","path":"/users/123"},"response":{"status":200,"body":"{\\"id\\": 123, \\"name\\": \\"Alice\\"}"}},
        {"request":{"method":"GET","path":"/users/123?fields=name&verbose=true"},"response":{"status":200,"body":"{\\"id\\": 123, \\"name\\": \\"Alice\\"}"}},
        {"request":{"method":"POST","path":"/items","body":"{\\"name\\": \\"widget\\"}"},"response":{"status":201,"body":"{\\"created\\": true, \\"payload\\": ${requestBody}}"}},
        {"request":{"method":"GET","path":"/status/404"},"response":{"status":404,"body":"{\\"message\\": \\"status 404\\"}"}},
        {"request":{"method":"GET","path":"/status/500"},"response":{"status":500,"body":"{\\"message\\": \\"status 500\\"}"}}
      ]
      """;

  static final List<Exchange> EXCHANGES = HttpContract.loadActions(JSON);
  static final List<Exchange> REQUESTS = EXCHANGES.subList(1, EXCHANGES.size());

  private TestActions() {}
}
