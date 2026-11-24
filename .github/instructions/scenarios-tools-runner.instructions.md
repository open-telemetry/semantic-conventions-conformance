---
applyTo: "scenarios/**,tools/runner/**"
---

# Code rules for scenarios, tools/runner

- Each conformance directory declares its runner wrapper and scenario commands in `conformance.yaml`, along with any expectations the domain permits. The wrapper supplies the registry pin, policies, and domain classification; the generic runner neither embeds those conventions nor infers the domain from the directory path.
