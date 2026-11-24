---
applyTo: "scenarios/**/ruby/**,tools/ruby/**"
---

# Code rules for Ruby scenarios and tooling

- Each Ruby scenario package owns a `Gemfile` and a committed `Gemfile.lock`; the launcher resolves the nearest directory containing both from the scenario directory.
