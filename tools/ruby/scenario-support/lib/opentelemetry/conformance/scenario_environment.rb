# frozen_string_literal: true

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

module OpenTelemetry
  module Conformance
    # Access to values supplied by the conformance runner.
    module ScenarioEnvironment
      module_function

      # Returns the nonblank environment value or raises a named error.
      def require(name)
        value = ENV[name]
        if value.nil? || value.strip.empty?
          raise KeyError, "required environment variable is missing: #{name}"
        end

        value
      end
    end
  end
end
