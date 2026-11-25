---
applyTo: "scenarios/browser/js/chrome/opentelemetry-browser-instrumentation/**"
---

# Code rules for scenarios/browser/js/chrome/opentelemetry-browser-instrumentation

- Each measured Chrome page registers only the browser instrumentation module it exercises, so its scenario report contains one instrumentation scope.
