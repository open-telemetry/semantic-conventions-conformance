# OBI conformance scenarios

[OpenTelemetry eBPF Instrumentation (OBI)](https://github.com/open-telemetry/opentelemetry-ebpf-instrumentation)
instruments a process from outside it, so an OBI directory runs the same
uninstrumented workload as every other implementation of its library, with
no SDK and no agent in the process, and wraps the run command instead:

```yaml
instrumentation_library: go.opentelemetry.io/obi
setup: otel-conformance-obi install -- otel-conformance-go build
scenarios:
  server:
    run: otel-http-drive --serve otel-conformance-obi run build/scenario
```

A directory is `<library>/obi/<side>/`, beside the library's other
implementations, so the report compares OBI with them library by library.

## `otel-conformance-obi`

`install [-- COMMAND...]` downloads the release pinned in
[`versions.env`](src/otel_conformance_obi/versions.env) into
`~/.cache/otel-conformance/obi/<version>/`, then runs `COMMAND`, which is the
directory's own build step: `setup:` is one command.

`run [--exe GLOB] [--args GLOB] COMMAND...` runs a scenario:

1. Starts `COMMAND` with `OTEL_CONFORMANCE_GATE` naming a named pipe.
2. Waits for the scenario to reach the gate: before its workload, the
   scenario opens the pipe and reads it until end of file, which cannot come
   while the launcher holds the write end. In Go the gate is
   [`scenario.WaitAtGate`](../go/scenario).
3. Starts OBI with [`obi.yaml`](src/otel_conformance_obi/obi.yaml) selecting
   processes by OBI's own process match: `--exe` on the resolved executable
   path, `--args` on the command line without `argv[0]`. Without either it
   selects `COMMAND`'s resolved executable, which is exact for a binary run
   directly. A scenario behind a wrapper names what the wrapper finally runs,
   usually with `--args`: the Python interpreter and the Java runtime are the
   same executable as the mock server and every other scenario.
4. Closes the pipe, releasing the scenario, once OBI's
   `obi_instrumented_processes` internal metric counts a process. OBI raises
   it after it registered the process, and only processes the selector
   matches are counted, so the first request is measured.
5. After `COMMAND` exits, keeps OBI running for the settle period, longer than
   both the span batch delay and the metric export interval, then stops it.
   OBI does not export what it still buffers when it is stopped.

The gate exists because OBI finds new processes by polling `/proc` and then
attaches from user space, which takes about a second, while a scenario's whole
workload can finish in less than 100 ms. Starting OBI first and running the
scenario unheld measures nothing.

`run` exits with `COMMAND`'s status. It fails instead when the scenario exits
before or never reaches the gate, when OBI exits before it is stopped, or when
the scenario exits before OBI attached to it, so a missing signal in the
report is never a crashed agent.

OBI needs root and a Linux kernel with BTF. The launcher runs it with
`sudo -n` when it is not root, which the GitHub-hosted runners allow. `install`
fails on any other platform, and without root or passwordless `sudo -n`, so
the runner stops at `setup:` instead of recording an empty run over the
committed `data.json`.

## Configuration

[`obi.yaml`](src/otel_conformance_obi/obi.yaml) is an OBI Config v2 document.
`run` substitutes `${OBI_PROCESS_MATCH}`, `${OBI_INTERNAL_METRICS_PORT}` (a free
local port for the internal metrics endpoint readiness is read from),
`${OTEL_EXPORTER_OTLP_ENDPOINT}` and `${OBI_METRIC_EXPORT_INTERVAL}` and passes
the result to `obi -config`. It
selects every attribute OBI can emit (`attributes.select: {"*": {include:
["*"]}}`) and every HTTP payload extractor with 64 KiB capture buffers, so a
run measures the most OBI can say, not its default subset.

`wakeup_len: 0` makes the kernel wake OBI's ring-buffer reader on every event.
Any other value sizes the wakeup threshold by the Go tracer's event, which the
generic tracer's smaller HTTP event never reaches, so a single request is only
read by a fallback poll every 3 s, and OBI drops what is still in the ring
buffer when it stops.

A replacement template must keep the internal metrics endpoint on
`${OBI_INTERNAL_METRICS_PORT}`: readiness is read from it.

| Variable | |
| --- | --- |
| `OTEL_CONFORMANCE_OBI_BINARY` | an OBI binary to use instead of the pinned release |
| `OTEL_CONFORMANCE_OBI_CONFIG` | another config template, for example one adding `daemon.logging.debug_trace_output: text` |
| `OTEL_CONFORMANCE_OBI_READY_TIMEOUT` | seconds to wait for the scenario to reach the gate, and again for OBI to attach to it (60) |
| `OTEL_CONFORMANCE_OBI_SETTLE` | seconds OBI keeps running after `COMMAND` exits (3) |

OBI logs to the launcher's standard error, so the runner shows it next to the
scenario's own output when a scenario fails. Standard output stays the
scenario's.
