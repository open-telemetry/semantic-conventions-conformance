---
applyTo: "tools/runner/**"
---

# Code rules for tools/runner

- In coverage models generated from Weaver v2, mark every entity identity attribute as required because those entries have no requirement levels. Preserve the registry's declared levels for entity description attributes.
- Persist a working-tree coverage model only when its key accounts for the inputs Weaver reads, including transitive local registry dependencies and applicable resolver configuration. Resolve without persistent reuse when inputs cannot be tracked, such as published manifests or remote dependencies. Never put override registries on the pinned cache path.
- The working-tree digest includes the paths and contents of visible YAML definitions and honors Weaver's symlink behavior. Refuse a semantic-convention cache at or visibly below any registry Weaver reads; a cache under a hidden directory is allowed where Weaver skips it.
- Publish cached coverage models atomically from a staging file on the destination filesystem, with separate retention limits for pinned and working-tree entries. If the working-tree digest changes during generation, do not persist the resulting model under the original key.
- An `if_present` span attribute check allows omission, but a value emitted and rejected by Weaver still counts as present and cannot satisfy the check. Diagnostics must distinguish rejection from omission and show the rejected value.
- Before writing committed coverage, normalize run-specific endpoint ports in span names consistently across runner and Weaver findings, including messages that quote the name. Preserve the emitted names on raw span samples.
