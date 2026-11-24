---
applyTo: ".github/**"
---

# Code rules for .github

- Renovate major upgrades get individual PRs and are not restricted to the weekly update window. Non-major Docker updates use the Docker group regardless of the detecting manager, including workflow and custom-manager images. The fallback patch group applies only when no more specific group takes over.
