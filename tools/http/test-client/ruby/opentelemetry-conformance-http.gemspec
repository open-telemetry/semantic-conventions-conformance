# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

require_relative "lib/opentelemetry/conformance/http/version"

Gem::Specification.new do |spec|
  spec.name = "opentelemetry-conformance-http"
  spec.version = OpenTelemetry::Conformance::HTTP::VERSION
  spec.authors = ["OpenTelemetry Authors"]
  spec.summary = "Shared HTTP semantic convention conformance contract"
  spec.homepage = "https://github.com/open-telemetry/semantic-conventions-conformance"
  spec.license = "Apache-2.0"
  spec.required_ruby_version = ">= 3.0"
  spec.files = Dir["lib/**/*.rb", "README.md"]
  spec.require_paths = ["lib"]

  spec.add_development_dependency "minitest", "~> 5.0"
  spec.add_development_dependency "rake", "~> 13.0"
end
