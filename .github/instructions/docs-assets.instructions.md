---
applyTo: "docs/assets/**"
---

# Code rules for docs/assets

- Group findings by attribute key when present, including `context.missing_attribute` for GenAI expected-attribute findings. Fall back to the message only when there is no key, and do not list an expected absence separately if its attribute coverage row already represents it.
- Use a neutral progress fill on coverage summary tiles and put the requirement-level swatch in the label. The signals list may use requirement-level fills when its legend explains them.
- When multiple runners report the same signal, check that its kind and base attribute declarations agree, but merge refinement-only attribute names for display. Show them as a distinct unscored group, not as a registry requirement level or part of base coverage.
- Heatmap emission indicators expose both emitted and not-emitted states to assistive technology independently of color or tooltips. A truncated target column label retains the full target name in the link's accessible name.
- When a report view is replaced, dispose of its view-specific observers and tracking callbacks so detached controls and heatmaps are no longer observed. A mirrored scroll rail must ignore programmatic scroll echoes that would overwrite newer user input.
