# The site

A static page over the aggregated data. `index.html` loads ES modules straight from `assets/`,
and the data layer is one `fetch` of `data/conformance.json`.

`data/conformance.json` is **generated — do not edit it by hand.** It is written by
`otel-conformance-report build` (see [`tools/report`](../tools/report)) and rebuilt
nightly by the [`Report`](../.github/workflows/report.yml) workflow, which opens a
pull request when it changed.

|                         |                                                           |
|-------------------------|-----------------------------------------------------------|
| `index.html`            | the shell: masthead, and the one `<script type="module">` |
| `assets/app.js`         | the hash router, and the provenance line in the footer    |
| `assets/data.js`        | fetch, and the index every view reads from                |
| `assets/ui.js`          | the element helpers                                       |
| `assets/views/`         | one module per route                                      |
| `data/conformance.json` | generated, do not edit by hand                            |

Serve locally with `python -m http.server -d docs`, then open
<http://localhost:8000>.

The browser compares signals by type and name. If two runners provide conflicting
declarations, loading fails rather than comparing targets against the wrong
registry. Coverage interpretation is documented in [`tools/report`](../tools/report).

The site has no runtime dependencies. Development checks use Node's test runner,
jsdom for DOM behavior, and Prettier:

```sh
npm --prefix docs ci --ignore-scripts
npm --prefix docs test
npm --prefix docs run format:check
```

`npm --prefix docs run format` formats the site sources and tests. The Pages
workflow publishes only `index.html`, `assets/`, and `data/`.
