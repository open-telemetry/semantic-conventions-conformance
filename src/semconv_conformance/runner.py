# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared pipeline runner used by the conformance domains."""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from semconv_conformance.locations import ScenarioLocation
from semconv_conformance.weaver import ensure_semconv_registry, ensure_weaver

if TYPE_CHECKING:
    from semconv_conformance.data_files import GeneratedScenarioData
    from semconv_conformance.language_adapters import DomainLanguageAdapters
    from semconv_conformance.otlp_bridge import OtlpHttpBridge
    from semconv_conformance.parse_results import ScenarioResult

logger = logging.getLogger(__name__)


class PipelineHook(Protocol):
    """Bracket a scenario run with setup/teardown around the core pipeline.

    `on_start` runs after dependency install but before Weaver launches and
    the scenario executes; `on_end` runs in the `finally` block of the
    outer pipeline, after Weaver and the OTLP bridge (if any) are stopped.
    Domains use this to manage extra local infrastructure their scenarios
    depend on.
    """

    def on_start(self, location: ScenarioLocation, state: PipelineState) -> None: ...

    def on_end(self, state: PipelineState) -> None: ...


class RunnerError(Exception):
    def __init__(
        self,
        message: str,
        exit_code: int = 1,
        show_available_scenarios: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
        self.show_available_scenarios = show_available_scenarios


@dataclass
class PipelineState:
    weaver_proc: subprocess.Popen | None = None
    otlp_http_bridge: OtlpHttpBridge | None = None
    mock_proc: subprocess.Popen | None = None


class DomainConfig(Protocol):
    """Structural interface the pipeline runner needs from a conformance domain.

    :class:`~semconv_conformance.domain.Domain` satisfies this protocol
    directly — no field-forwarding wrapper is built at runtime.
    """

    @property
    def domain_dir(self) -> Path: ...
    @property
    def language_adapters(self) -> DomainLanguageAdapters: ...
    @property
    def parse_result_dir(self) -> Callable[[Path, ScenarioLocation], ScenarioResult | None]: ...
    @property
    def generate_single_scenario_data(self) -> Callable[[ScenarioLocation], GeneratedScenarioData | None]: ...
    @property
    def default_otlp_protocol(self) -> Callable[[ScenarioLocation], str]: ...
    @property
    def extra_env(self) -> dict[str, str]: ...
    @property
    def weaver_health_timeout(self) -> int: ...
    @property
    def inactivity_timeout(self) -> int: ...
    @property
    def hook(self) -> PipelineHook | None: ...
    @property
    def extra_error_types(self) -> tuple[type[Exception], ...]: ...


# ── Utility functions ────────────────────────────────────────────────


def allocate_free_tcp_ports(count: int) -> list[int]:
    """Ask the OS for unused loopback TCP ports to reduce collisions in CI."""
    sockets: list[socket.socket] = []
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("127.0.0.1", 0))
            sockets.append(sock)
        return [sock.getsockname()[1] for sock in sockets]
    finally:
        for sock in sockets:
            sock.close()


def is_healthy(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        # Expected during startup polling: connection refused, 503 while
        # warming up, socket timeout. Anything else should propagate.
        return False


def wait_for_health(url: str, timeout: int, label: str, proc: subprocess.Popen | None = None) -> None:
    poll_interval = 0.1
    deadline = time.monotonic() + timeout
    start = time.monotonic()
    while True:
        if is_healthy(url):
            logger.info("%s ready after %.1fs", label, time.monotonic() - start)
            return
        if proc and proc.poll() is not None:
            raise RunnerError(f"{label} process died during startup")
        if time.monotonic() >= deadline:
            raise RunnerError(f"{label} failed to become ready after {timeout}s")
        time.sleep(poll_interval)


def stop_process(proc: subprocess.Popen | None, label: str) -> None:
    if proc and proc.poll() is None:
        logger.info("Stopping %s (PID %d)...", label, proc.pid)
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            logger.warning("%s did not exit 30s after terminate(); killing.", label)
            proc.kill()
            proc.wait()


# ── Pipeline ─────────────────────────────────────────────────────────


def _prepare_results_dir(result_dir: Path) -> None:
    if result_dir.exists():
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)


def _build_weaver_command(
    weaver_bin: Path,
    result_dir: Path,
    *,
    registry: str,
    weaver_port: int,
    admin_port: int,
    inactivity_timeout: int,
    extra_args: list[str],
) -> list[str]:
    command = [str(weaver_bin), "registry", "live-check"]
    if registry:
        command.extend(["-r", registry])
    command.extend(
        [
            "--format",
            "json",
            "--output",
            str(result_dir),
            "--otlp-grpc-port",
            str(weaver_port),
            "--admin-port",
            str(admin_port),
            "--inactivity-timeout",
            str(inactivity_timeout),
        ]
    )
    command.extend(extra_args)
    return command


def _stop_weaver(admin_port: int, weaver_proc: subprocess.Popen) -> int:
    # Give Weaver a brief grace period to drain the last batch of OTLP
    # traffic before asking it to stop — otherwise its summary statistics
    # can come up short on fast scenarios.
    time.sleep(1)
    if weaver_proc.poll() is None:
        try:
            urllib.request.urlopen(
                urllib.request.Request(f"http://localhost:{admin_port}/stop", method="POST"),
                timeout=5,
            )
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            logger.warning("Weaver admin /stop failed (%s); falling back to terminate().", e)
            weaver_proc.terminate()
    return weaver_proc.wait(timeout=30)


def _validate_weaver_output(
    location: ScenarioLocation,
    results_dir: Path,
    weaver_exit: int,
    has_statistics: bool,
) -> None:
    if not any(results_dir.glob("**/*.json")):
        raise RunnerError(
            f"Weaver produced no output for scenario: {location.scenario_id}",
        )

    if weaver_exit != 0 and not has_statistics:
        raise RunnerError(
            f"Weaver produced partial output (missing statistics) and exited non-zero for scenario: {location.scenario_id}",
            exit_code=weaver_exit or 1,
        )
    if weaver_exit != 0:
        logger.warning(
            "Note: Weaver returned a non-zero exit code because violations were reported; "
            "continuing with captured statistics.",
        )


def _build_test_environment(
    location: ScenarioLocation,
    otlp_protocol: str,
    weaver_port: int,
    otlp_http_bridge: OtlpHttpBridge | None,
    extra_env: dict[str, str] | None,
) -> dict[str, str]:
    env = {
        **os.environ,
        "OTEL_TRACES_EXPORTER": "otlp",
        "OTEL_METRICS_EXPORTER": "otlp",
        "OTEL_LOGS_EXPORTER": "otlp",
        "OTEL_BSP_SCHEDULE_DELAY": "200",
        "OTEL_BLRP_SCHEDULE_DELAY": "200",
        "OTEL_METRIC_EXPORT_INTERVAL": "1000",
    }
    if extra_env:
        env.update(extra_env)

    if otlp_protocol == "grpc":
        env.update(
            {
                "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
                "OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{weaver_port}",
            }
        )
        return env

    if otlp_protocol == "http/protobuf" and otlp_http_bridge is not None:
        env.update(
            {
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_EXPORTER_OTLP_ENDPOINT": otlp_http_bridge.endpoint,
                "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": f"{otlp_http_bridge.endpoint}/v1/traces",
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": f"{otlp_http_bridge.endpoint}/v1/metrics",
                "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": f"{otlp_http_bridge.endpoint}/v1/logs",
            }
        )
        return env

    raise RunnerError(f"Unsupported otlp_protocol '{otlp_protocol}' for scenario: {location.scenario_id}")


def _load_metadata(domain_dir: Path, location: ScenarioLocation) -> dict[str, object]:
    metadata_file = domain_dir / location.lang / location.library / "metadata.json"
    if not metadata_file.is_file():
        return {}
    return json.loads(metadata_file.read_text(encoding="utf-8"))


def _write_generated_data(generate_fn: Callable, location: ScenarioLocation) -> None:
    result = generate_fn(location)
    if result is None:
        raise RunnerError(f"Could not parse Weaver results for scenario: {location.scenario_id}")

    # Leaving the committed file untouched here would let a scenario that
    # exports nothing at all pass CI's `git diff --exit-code` check, so a
    # silently broken instrumentation has to be a hard failure.
    if not result.has_relevant_data:
        raise RunnerError(
            f"Scenario produced no telemetry matching the domain's semantic conventions: "
            f"{location.scenario_id}. Check that the scenario app ran and that its exporter "
            f"is pointed at Weaver."
        )

    result.path.parent.mkdir(parents=True, exist_ok=True)
    result.path.write_text(json.dumps(result.data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    logger.info("Updated %s", result.path)


def _start_weaver(
    domain: DomainConfig,
    state: PipelineState,
    results_dir: Path,
    registry: str,
    weaver_port: int,
    admin_port: int,
    extra_weaver_args: list[str],
) -> None:
    """Launch the Weaver live-check collector and wait for it to become healthy."""
    logger.info("=== Starting Weaver on port %d ===", weaver_port)
    weaver_cmd = _build_weaver_command(
        ensure_weaver(),
        results_dir,
        registry=registry,
        weaver_port=weaver_port,
        admin_port=admin_port,
        inactivity_timeout=domain.inactivity_timeout,
        extra_args=extra_weaver_args,
    )
    state.weaver_proc = subprocess.Popen(weaver_cmd)
    wait_for_health(
        f"http://localhost:{admin_port}/health",
        domain.weaver_health_timeout,
        "Weaver",
        state.weaver_proc,
    )


def _maybe_start_otlp_bridge(
    state: PipelineState,
    otlp_protocol: str,
    weaver_port: int,
    bridge_port: int,
) -> None:
    """Weaver only exposes OTLP gRPC; bridge HTTP/protobuf scenarios through a local proxy."""
    if otlp_protocol != "http/protobuf":
        return

    from semconv_conformance.otlp_bridge import OtlpHttpBridge

    logger.info("=== Starting OTLP HTTP bridge on port %d ===", bridge_port)
    state.otlp_http_bridge = OtlpHttpBridge(
        bridge_port,
        f"http://127.0.0.1:{weaver_port}",
    )
    state.otlp_http_bridge.start()
    wait_for_health(state.otlp_http_bridge.health_url, 10, "OTLP HTTP bridge")


def run_pipeline(
    domain: DomainConfig,
    location: ScenarioLocation,
    extra_weaver_args: list[str],
    weaver_port: int,
    admin_port: int,
    bridge_port: int,
    registry: str,
    state: PipelineState,
) -> None:
    """Run the full pipeline: setup, weaver, scenario, collect results."""
    metadata = _load_metadata(domain.domain_dir, location)

    adapter = domain.language_adapters.get(location.lang)
    if adapter is None:
        raise RunnerError(f"No adapter for language: {location.lang}")
    adapter.install_dependencies(location.library, location.ecosystem)

    if domain.hook:
        domain.hook.on_start(location, state)

    # Weaver uses an inactivity timeout; a long compile step in a
    # compiled-language scenario can cause it to shut down before the
    # scenario sends any data.
    adapter.prebuild_scenario(location.library)

    results_dir = location.results_dir(domain.domain_dir).resolve()
    _prepare_results_dir(results_dir)

    _start_weaver(domain, state, results_dir, registry, weaver_port, admin_port, extra_weaver_args)

    otlp_protocol = metadata.get("otlp_protocol", domain.default_otlp_protocol(location))
    if not isinstance(otlp_protocol, str):
        raise RunnerError(f"Invalid otlp_protocol in metadata for {location.scenario_id}")

    _maybe_start_otlp_bridge(state, otlp_protocol, weaver_port, bridge_port)

    env = _build_test_environment(location, otlp_protocol, weaver_port, state.otlp_http_bridge, domain.extra_env)

    logger.info("=== Running scenario: %s ===", location.scenario_id)
    scenario_run = domain.language_adapters.run_scenario_cmd(location, env)
    if not scenario_run.found:
        raise RunnerError(f"Scenario not found: {location.scenario_id}", show_available_scenarios=True)

    if state.weaver_proc is None:
        raise RunnerError("Weaver process was not started")
    weaver_exit = _stop_weaver(admin_port, state.weaver_proc)
    state.weaver_proc = None
    logger.info("=== Weaver exit code: %d ===", weaver_exit)
    logger.info("=== Results in: %s ===", results_dir)
    fresh_result = domain.parse_result_dir(results_dir, location)

    if scenario_run.exit_code != 0:
        raise RunnerError(
            f"Scenario process exited with code {scenario_run.exit_code}",
            exit_code=scenario_run.exit_code or 1,
        )

    has_statistics = fresh_result is not None and fresh_result.statistics is not None
    _validate_weaver_output(location, results_dir, weaver_exit, has_statistics)

    logger.info("=== Updating data file ===")
    _write_generated_data(domain.generate_single_scenario_data, location)


# ── Main ─────────────────────────────────────────────────────────────


def _print_available_scenarios(list_fn: Callable[[], list[str]]) -> None:
    available = list_fn()
    if available:
        logger.error("Available scenarios:")
        for scenario_id in available:
            logger.error("  %s", scenario_id)


def run_main(domain: DomainConfig) -> int:
    """Shared main() entry point for domain-specific run-scenario scripts."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    if len(sys.argv) < 4:
        command = Path(sys.argv[0]).name or "run-scenario"
        logger.error("Usage: %s <language> <library> <ecosystem> [weaver-args...]", command)
        _print_available_scenarios(domain.language_adapters.list_available_scenarios)
        return 1

    language, library, ecosystem = sys.argv[1], sys.argv[2], sys.argv[3]
    extra_weaver_args = sys.argv[4:]
    location = ScenarioLocation(lang=language, library=library, ecosystem=ecosystem)

    logger.info("Scenario: %s", location.scenario_id)

    state = PipelineState()

    try:
        weaver_port, admin_port, bridge_port = allocate_free_tcp_ports(3)
        registry = ensure_semconv_registry()
        run_pipeline(
            domain,
            location,
            extra_weaver_args,
            weaver_port,
            admin_port,
            bridge_port,
            registry,
            state,
        )
    except RunnerError as e:
        logger.error("ERROR: %s", e)
        if e.show_available_scenarios:
            _print_available_scenarios(domain.language_adapters.list_available_scenarios)
        return e.exit_code
    except domain.extra_error_types as e:
        logger.error("ERROR: %s", e)
        return 1
    finally:
        if state.otlp_http_bridge is not None:
            state.otlp_http_bridge.stop()
        stop_process(state.weaver_proc, "weaver")
        if domain.hook:
            domain.hook.on_end(state)

    return 0
