# Python conformance scenarios

`otel-conformance-python <scenario.py>` installs the global providers over
OTLP and loads no instrumentation, for scenarios whose telemetry needs
programmatic configuration rather than an environment variable. Zero-code
directories need nothing here: they run `opentelemetry-instrument`.

What it runs is an entry program in the implementation directory, which makes
that call and imports the shared scenario, reached through `PYTHONPATH`:

```yaml
env:
  PYTHONPATH: ..

scenarios:
  inference:
    run: uv run --frozen --project . otel-conformance-python inference.py
```

The launcher is installed into the scenario's own environment, as a path
dependency on this directory.
