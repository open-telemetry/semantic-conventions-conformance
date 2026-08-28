# The site

A static page over the committed report. No build step, no bundler, and no
dependencies: `index.html` loads ES modules straight from `assets/`, and the
whole of the data layer is one `fetch` of `data/conformance.json`.

| | |
| --- | --- |
| `index.html` | the shell: masthead, and the one `<script type="module">` |
| `assets/app.js` | the hash router, and the provenance line in the footer |
| `assets/data.js` | fetch, and the index every view reads from |
| `assets/ui.js` | the element helpers |
| `assets/views/` | one module per route |
| `data/conformance.json` | committed, written by `otel-conformance-report build` |

`data/conformance.json` is rebuilt nightly by the
[`Report`](../.github/workflows/report.yml) workflow, which opens a pull request
when it moved; publishing is a push to `main`. So a merge that moves a reduction
shows up on the site once that pull request lands, not with the merge itself.
