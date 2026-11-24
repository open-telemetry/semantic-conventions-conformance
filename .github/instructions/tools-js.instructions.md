---
applyTo: "tools/js/**"
---

# Code rules for tools/js

- For chunked browser OTLP uploads, forward the exact body byte count in `Content-Length` and omit `Transfer-Encoding`. An unreachable endpoint or a non-2xx export response must fail the scenario rather than count as a successful export.
