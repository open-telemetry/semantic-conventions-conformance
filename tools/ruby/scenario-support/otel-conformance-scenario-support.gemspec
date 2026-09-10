# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

Gem::Specification.new do |spec|
  spec.name = "otel-conformance-scenario-support"
  spec.version = "0.1.0"
  spec.summary = "Runtime support shared by Ruby conformance scenarios"
  spec.authors = ["OpenTelemetry Authors"]
  spec.license = "Apache-2.0"
  spec.files = Dir.chdir(__dir__) { Dir["lib/**/*.rb"] }
  spec.require_paths = ["lib"]
  spec.required_ruby_version = ">= 3.1"
end
