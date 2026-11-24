---
applyTo: "scenarios/http/**,tools/ruby/**"
---

# Code rules for scenarios/http, tools/ruby

- Each Ruby scenario package owns a `Gemfile` and a committed `Gemfile.lock`; the launcher resolves the nearest directory containing both from the scenario directory.
