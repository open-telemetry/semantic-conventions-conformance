/*
 * Copyright The OpenTelemetry Authors
 * SPDX-License-Identifier: Apache-2.0
 */
package io.opentelemetry.conformance.database.mongodb.reactive;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.mongodb.ServerAddress;
import java.util.List;
import org.junit.jupiter.api.Test;

class MongoReactiveScenarioTest {
  @Test
  void createsListenerWithConfiguredSeedsBeforeConnecting() {
    RuntimeException stopBeforeConnecting = new RuntimeException("listener factory invoked");

    RuntimeException thrown =
        assertThrows(
            RuntimeException.class,
            () ->
                MongoReactiveScenario.run(
                    "find",
                    servers -> {
                      assertEquals(List.of(new ServerAddress("127.0.0.1", 43210)), servers);
                      throw stopBeforeConnecting;
                    }));

    assertSame(stopBeforeConnecting, thrown);
  }
}
