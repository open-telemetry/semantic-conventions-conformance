# Python conformance scenarios

`otel-conformance-python <scenario.py>` installs the global providers over
OTLP and loads no instrumentation, for scenarios whose telemetry needs
programmatic configuration rather than an environment variable. Zero-code
directories need nothing here: they run `opentelemetry-instrument`.

What it runs is an entry program in the implementation directory, which makes
that call and imports the shared scenario beside it:

```yaml
scenarios:
  inference:
    run: uv run --frozen --project . otel-conformance-python inference.py
```

The entry program puts the shared directory on the path from its own location.
A declared `PYTHONPATH` will not do: the ambient environment wins over what
`conformance.yaml` declares, so a machine that already exports one replaces it.

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

The launcher is installed into the scenario's own environment, as a path
dependency on this directory.

Before normal SDK shutdown, the launcher force-flushes traces and logs, waits
for both, then force-flushes metrics. The shared bounded budget is 15 seconds;
a failure or timeout fails the scenario.

Programs started directly by upstream `opentelemetry-instrument` are not under
this launcher's control (not customizable in Python).

`otel-conformance-python-relock` is for maintainers. It is a separate command
because the launcher takes the scenario program as its only argument. From
anywhere in the repository, it runs `uv lock` (without `--upgrade`) in every
directory under `scenarios/` and `tools/` that has a committed `uv.lock`, so
only what the manifests and path dependencies require changes. Scenarios run
with `uv run --frozen`, which does not fail on a stale lock, so a lock left
behind by a change to this package is easy to miss. CI runs the command on
Renovate PRs and commits the result. CI pins the uv version, because uv can
rewrite the lock format. Use the same uv version when running it by hand:

```sh
otel-conformance-python-relock
```
