# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

module OpenTelemetry
  module Conformance
    # How a long-running scenario learns that the runner is finished with it.
    module ScenarioLifecycle
      module_function

      # Blocks until standard input closes, which is the driver's stop signal.
      def wait_for_eof(input = $stdin)
        nil while input.read(16_384)
      end
    end
  end
end
