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
