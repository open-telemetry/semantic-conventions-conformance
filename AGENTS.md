# Working in this repo

Read [README.md](README.md) first for what the repo is and how it is laid out.
Directory-specific rules live beside the code they govern — see
[`scenarios/gen-ai/AGENTS.md`](scenarios/gen-ai/AGENTS.md).

## Writing comments and docs

Prose here is read by maintainers of a dozen instrumentations, so keep it plain
and short. Anything an LLM wrote is held to the same bar as anything a person
wrote.

- **Comment only what is non-obvious.** A comment earns its place by explaining
  why the code is the way it is, or naming a constraint the reader cannot see. If
  it restates the line below it, delete it.
- **One or two plain sentences.** No aphorisms, no rhetorical build-up, no
  em-dash asides stacked on each other, no closing flourish. Say the thing.
- **Docstrings say what a function takes and returns**, not what it means for the
  project. Exported JavaScript functions get a JSDoc with `@param` and `@returns`.
- **Do not restate another file's rules.** Link to the file that owns them.
- **Name the source of truth.** Where a constant or vocabulary is duplicated
  across languages, the copy says which file it was copied from.
- **Mark generated files.** A file written by a tool says so, and says which
  command writes it, so nobody edits it by hand.

## Before opening a PR

- Run the tests for what you touched; `.github/workflows/runner.yml` lists them.
- `ruff check .` and `python -m pyright` cover the Python.
- Commit regenerated files (`data.json`, `uv.lock`, `docs/data/conformance.json`)
  in the same change as what moved them.
