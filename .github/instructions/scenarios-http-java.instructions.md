---
applyTo: "scenarios/http/java/**"
---

# Code rules for scenarios/http/java

- Java HTTP OBI scenarios run the workload without an in-process SDK or agent of their own and wait at the `otel-conformance-obi` startup gate before making or serving measured requests.
