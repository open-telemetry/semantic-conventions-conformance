---
applyTo: "tools/obi/**"
---

# Code rules for tools/obi

- Verify a downloaded OBI archive against the pinned SHA-256 for the host architecture before publishing the executable to the install cache. A failed verification must leave no executable available for later privileged use. Run any supplied build command only after the pinned executable is available.
- Report invalid OBI timeout settings and unexpected FIFO-open errors as launcher-prefixed `LauncherError` diagnostics, not raw tracebacks. `ENXIO` while opening the gate means no reader has arrived yet; retry subject to the readiness checks.
- When an OBI run installs process-wide signal handlers, restore the previous handlers on exit, including failure. If no live scenario remains to receive a forwarded signal, preserve the previous signal behavior rather than swallowing it.
- If no OBI process selector is supplied, escape glob metacharacters in the resolved workload executable path so it matches literally. Explicit `--exe` and `--args` values remain caller-supplied globs.
