---
applyTo: "scenarios/http/**,tools/http/**,tools/js/**"
---

# Code rules for scenarios/http, tools/http, tools/js

- HTTP scenario npm packages declare repository-owned dependencies with local `file:` references rather than registry ranges or implicit sibling workspace resolution. When npm installs a path dependency as a copy, shared tooling test scripts target the source package so they exercise checkout edits.
