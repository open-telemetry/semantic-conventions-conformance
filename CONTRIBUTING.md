# Contributing

Thanks for your interest in improving the semantic conventions conformance
scenarios! This guide covers local setup, running a single scenario, the
per-library layout, how CI discovers scenarios, and how the committed
`data-*.json` coverage files get regenerated.

For a high-level overview of what the pipeline does, see the
[root README](README.md#how-it-works).

## Table of contents

- [Repository layout](#repository-layout)
- [Setting up locally](#setting-up-locally)
- [Running a single scenario](#running-a-single-scenario)
- [The per-library directory](#the-per-library-directory)
- [`metadata.json` reference](#metadatajson-reference)
- [`ecosystems.json` reference](#ecosystemsjson-reference)
- [Regenerating `data-<eco>.json`](#regenerating-data-ecojson)
- [CI matrix generation](#ci-matrix-generation)
- [Adding a new library](#adding-a-new-library)
- [Adding a new ecosystem](#adding-a-new-ecosystem)
- [Adding a new language](#adding-a-new-language)
- [Pinned upstream versions](#pinned-upstream-versions)
- [Lint and license headers](#lint-and-license-headers)

## Repository layout

```
<repo>/
├── http/                       # HTTP semantic conventions domain
│   ├── ecosystems.json
│   ├── README.md
│   └── <language>/<library>/   # One directory per (language, library)
├── src/semconv_conformance/    # Shared Python framework + per-domain entry points
├── .github/
│   ├── scripts/                # check-license-headers.py
│   └── workflows/              # conformance-ci.yml, _run-language-scenarios.yml, …
├── pyproject.toml              # CLI entry points (see below)
└── versions.env                # Pinned WEAVER_VERSION / SEMCONV_VERSION
```

The framework is language- and domain-agnostic; `http` and `python` are simply
the first domain and language to land. Additional languages and domains are
added as described in [Adding a new language](#adding-a-new-language).

## Setting up locally

Requirements:

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) — used to create the isolated per-scenario
  environments and to run the linters
- `git` on `PATH` (Weaver fetches the semantic-conventions registry via git)
- The language toolchain for whichever scenarios you intend to run

Weaver itself is downloaded automatically by the scenario runner; you do not
need to install it by hand.

Install the framework in editable mode:

```sh
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e '.[otlp-bridge]'
```

The `otlp-bridge` extra pulls in `grpcio` and `opentelemetry-proto` so the
runner can transcode OTLP HTTP/protobuf traffic from libraries that only speak
HTTP to Weaver's gRPC endpoint. Install it unless you know you don't need it.

Console entry points:

- `http-run-scenario <language> <library> <ecosystem>` — run one HTTP scenario.
- `semconv-ci-matrix <domain>|all` — emit the CI scenario matrix.

## Running a single scenario

Scenarios are identified by the three-tuple `(language, library, ecosystem)`
— passed as separate arguments so library slugs are free to contain hyphens
(e.g. `otelhttp-client`):

```sh
http-run-scenario python flask otelcontrib
```

Running a scenario:

1. Installs language-specific dependencies (in an isolated cache directory
   where applicable — e.g. a per-library `.venv` for Python).
2. Builds the scenario app when the language requires it.
3. Starts Weaver `registry live-check` on a free local port.
4. Runs the scenario app. The instrumented library exports telemetry over
   OTLP to Weaver.
5. Parses Weaver's JSON output and **rewrites
   `<domain>/<language>/<library>/data-<eco>.json`** with the observed
   coverage.

CI runs the exact same commands and then verifies with `git diff --exit-code`
that the committed `data-*.json` files are up to date.

## The per-library directory

Every library lives at `<domain>/<language>/<library>/`. The file set varies
slightly by language, but the contract is consistent:

| File                            | Required? | Notes                                                              |
| ------------------------------- | --------- | ------------------------------------------------------------------ |
| `metadata.json`                 | yes       | Library metadata; see schema below.                                |
| `data-<eco>.json`               | yes (1+)  | Committed coverage output. One per supported ecosystem.            |
| `results/`                      | no        | Where Weaver writes raw results. Generated; `.gitignore`d.         |
| **Python:** `run_<eco>.py`      | yes       | Scenario app entry point.                                          |
| **Python:** `requirements-<eco>.txt` | yes  | Direct dependencies, pinned.                                       |
| **Python:** `requirements-<eco>.lock` | yes | `uv pip compile` output; what the runner installs.                 |

The ecosystem slug (`<eco>`) identifies the instrumentation source. Today the
only one is `otelcontrib`; a library that emits semantic conventions itself
would use `native`. Ecosystems are declared in
[`<domain>/ecosystems.json`](#ecosystemsjson-reference).

Example — `http/python/flask/`:

```
data-otelcontrib.json
metadata.json
requirements-otelcontrib.lock
requirements-otelcontrib.txt
run_otelcontrib.py
```

Code shared across libraries in a given language lives in
`<domain>/<language>/shared/`. How each scenario wires it in is visible at the
top of the scenario's entry-point file or build manifest.

Lock files are compiled with `uv`, using the long `--output-file=` form because
that is what Renovate's `pip-compile` manager can parse:

```sh
uv pip compile http/python/flask/requirements-otelcontrib.txt \
  --output-file=http/python/flask/requirements-otelcontrib.lock --universal
```

The lock file is what Renovate tracks, so every Python scenario needs one — a
scenario shipping only a `.txt` would go unmanaged.

## `metadata.json` reference

```jsonc
{
  "display_name": "Flask",                          // required
  "repo": "pallets/flask",                          // recommended — upstream library repo
  "version_packages": {                             // optional — for version tracking
    "otelcontrib": "opentelemetry-instrumentation-flask"
  },
  "opt_in_env_vars": {                              // optional
    "otelcontrib": "OTEL_SEMCONV_STABILITY_OPT_IN=http"
  },
  "otlp_protocol": "http/protobuf",                 // optional — "grpc" (default) or "http/protobuf"
  "ci_runs_on": "windows-latest"                    // optional — overrides the default runner
}
```

- **`display_name`** is the only required field. It controls how the library
  appears in reports.
- **`opt_in_env_vars`** declares the environment variable an instrumentation
  needs in order to emit stable semantic conventions. The value is a
  `KEY=value` string. It is descriptive — the scenario itself is responsible
  for setting the variable (for Python, `shared/scenario_harness.py` does it)
  — and it is recorded alongside the results so the opt-in requirement stays
  visible.
- **`otlp_protocol`** — set to `"http/protobuf"` when the instrumentation
  cannot export OTLP gRPC. The runner's OTLP bridge will transcode to gRPC
  before forwarding to Weaver.
- **`version_packages`** — the package name to read the installed
  instrumentation version from, per ecosystem.
- **`ci_runs_on`** — override for the default GitHub runner (e.g.
  `windows-latest` for Windows-only instrumentations).

## `ecosystems.json` reference

One per domain, at `<domain>/ecosystems.json`. Each ecosystem maps to a
display name and, optionally, a per-language source repository. Illustrative —
`http/ecosystems.json` currently declares `otelcontrib` alone:

```jsonc
{
  "otelcontrib": {
    "display_name": "OTel Contrib",
    "repos": {
      "python": "open-telemetry/opentelemetry-python-contrib"
    }
  },
  "native": {                        // no `repos`: the library is its own source
    "display_name": "Native"
  }
}
```

`repos` records where each ecosystem's instrumentation for a given language
lives, so results can be linked back to their source. Add a language's entry
when that language's scenarios land.

## Regenerating `data-<eco>.json`

The `data-<eco>.json` files are committed and treated as the recorded
conformance results. To regenerate one:

```sh
http-run-scenario python flask otelcontrib
# rewrites http/python/flask/data-otelcontrib.json in place
```

There is no regen-only flag — running the scenario always rewrites the data
file from the Weaver run.

When CI runs, a `git diff --exit-code -- "<lang>/<lib>/data-*.json"` step
fails the job if the committed file does not match what the scenario produced.
If that happens, re-run the scenario locally and commit the refreshed file.

## CI matrix generation

Per-language scenario matrices are generated by the `semconv-ci-matrix`
console script, which lives in
[`src/semconv_conformance/ci_matrix.py`](src/semconv_conformance/ci_matrix.py).

Discovery globs `<domain>/<language>/<library>/data-*.json`. The parent
directory is the library; the stem after `data-` is the ecosystem. Every
discovered entry is emitted as one row in a single flat `matrix` output
consumed by
[`_run-language-scenarios.yml`](.github/workflows/_run-language-scenarios.yml):

```yaml
strategy:
  matrix: ${{ fromJson(needs.discover-scenarios.outputs.matrix) }}
```

Because discovery is purely file-system driven, **adding a new library
requires no CI changes** — the matrix picks it up on the next push.

The runner for each row defaults per language and may be overridden by
`ci_runs_on` in `metadata.json`.

## Adding a new library

1. Create `<domain>/<language>/<library>/`.
2. Write `metadata.json` (see schema above).
3. Add the scenario entry point and dependency manifest for each ecosystem
   you're covering — `run_<eco>.py` plus `requirements-<eco>.txt` and its
   compiled `.lock` for Python.
4. Run the scenario locally:

   ```sh
   <domain>-run-scenario <language> <library> <ecosystem>
   ```

   This generates `data-<eco>.json`.
5. Commit `metadata.json`, the scenario/dependency files, and the generated
   `data-<eco>.json`. Do not commit the `results/` output directory.
6. Open a PR. CI will re-run the scenario on GitHub-hosted runners.

Tips:

- If the instrumentation requires an opt-in env var, declare it in
  `opt_in_env_vars` *before* running the scenario.
- If the instrumentation can only speak OTLP HTTP/protobuf, set
  `otlp_protocol: "http/protobuf"` in `metadata.json`.
- If the scenario can only run on a specific OS, set `ci_runs_on` in
  `metadata.json` to override the default GitHub runner for that library.
- Use an existing library directory in the same language as your template.

## Adding a new ecosystem

Ecosystems are implicit: they show up wherever a `data-<eco>.json` or
`<eco>.*` entry-point file exists. To add one:

1. Pick a stable slug (e.g. `openinference`).
2. Add an entry to the relevant `<domain>/ecosystems.json` with its display
   name and any per-language repos.
3. Add `<eco>.*` and dependency files to whichever libraries it covers.

No framework code changes are needed.

## Adding a new language

Languages are opt-in, so a language's adapter and its scenarios land together:

1. Add the adapter module under
   [`src/semconv_conformance/language_adapters/`](src/semconv_conformance/language_adapters/)
   and register it in that package's `_BUILDERS` map.
2. Add the language to
   [`src/semconv_conformance/languages.json`](src/semconv_conformance/languages.json)
   with its display name and default CI runner. A language directory with no
   registry entry is silently skipped.
3. Add its toolchain setup step to
   [`.github/actions/setup-language/action.yml`](.github/actions/setup-language/action.yml),
   guarded by `if: inputs.language == '<lang>'`. If the toolchain version is
   pinned inline, add a matching custom manager to
   [`.github/renovate.json5`](.github/renovate.json5) so it stays updated.
4. Add a `packageRules` entry in [`.github/renovate.json5`](.github/renovate.json5)
   grouping the language's manager(s) — alongside the existing `python-minor`
   group — so one ecosystem's failing update doesn't block the others.
5. Add the language's entry to each relevant ecosystem's `repos` map in
   `<domain>/ecosystems.json`.
6. Add the language to the CodeQL matrix in
   [`.github/workflows/codeql.yml`](.github/workflows/codeql.yml) if CodeQL
   supports it.
7. Add at least one library under `<domain>/<language>/` so the new adapter is
   actually exercised by CI.

Config in this repo is kept to what the committed scenarios actually use, so
each of these files grows with the language rather than carrying entries for
languages that haven't landed.

## Pinned upstream versions

Both Weaver and the semantic conventions registry are pinned in
[`versions.env`](versions.env):

```sh
WEAVER_VERSION=…
SEMCONV_VERSION=…
```

Renovate keeps these up to date via the custom regex manager in
[`.github/renovate.json5`](.github/renovate.json5). Bumping them changes only
`versions.env` itself, but a new Weaver or registry version can legitimately
change what a scenario reports — so re-run the affected scenarios and commit any
resulting `data-*.json` updates in the same PR.

## Lint and license headers

[`lint.yml`](.github/workflows/lint.yml) runs `ruff check`, `ruff format
--check`, and `mypy`, using the versions pinned in `pyproject.toml`:

```sh
uv run --extra dev ruff check src http .github/scripts
uv run --extra dev ruff format --check src http .github/scripts
uv run --extra dev mypy src .github/scripts
```

ruff covers the scenario tree as well as the framework. `mypy` does not, because
scenario code imports instrumentation packages that only exist inside that
scenario's per-library environment.

Every source file carries the two-line Apache-2.0 header:

```
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
```

(or the `//` equivalent for languages with C-style comments). This is enforced
by [`.github/scripts/check-license-headers.py`](.github/scripts/check-license-headers.py),
which you can run locally:

```sh
python .github/scripts/check-license-headers.py
```
