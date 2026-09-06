# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The conformance session — a plain library, free of pytest.

It owns the server and weaver lifecycles so a pytest fixture and the
CLI are thin wrappers over the same entry point, and it never raises for
something a scenario got wrong: that lands in ``ScenarioReport.failures`` and
the caller decides what it means. A broken harness still raises.
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Callable,
    Generator,
    Mapping,
    Protocol,
    TypeVar,
)

from ._checks import check
from ._coverage import coverage
from ._env import (
    METRIC_EXPORT_INTERVAL_MILLIS,
    build_env,
    timeout_seconds,
)
from ._registry import check_weaver
from ._server import Server
from ._spec import (
    PackageSpec,
    ScenarioSpec,
    ServerSpec,
    SpecError,
    WeaverSpec,
    load_spec,
)

if TYPE_CHECKING:
    from opentelemetry.test.weaver_live_check import LiveCheckReport

logger = logging.getLogger(__name__)

# Generous: a cold scenario subprocess can spend a while importing a large
# framework before it emits anything. Overridable through the environment.
_WEAVER_INACTIVITY_TIMEOUT = (
    "OTEL_CONFORMANCE_WEAVER_INACTIVITY_TIMEOUT",
    300.0,
)
_WEAVER_STOP_TIMEOUT = ("OTEL_CONFORMANCE_WEAVER_STOP_TIMEOUT", 120.0)
_SCENARIO_TIMEOUT = ("OTEL_CONFORMANCE_SCENARIO_TIMEOUT", 600.0)

# Both relative to the conformance directory. The raw reports are throwaway;
# the data file is meant to be committed and diffed.
DEFAULT_REPORT_DIR = Path("output") / "weaver-reports"
DEFAULT_DATA_FILE = Path("data.json")

# Fallback only: a config declared by the caller or the package replaces it.
RUNNER_WEAVER_DEFAULTS = WeaverSpec(
    config=str(Path(__file__).parent / "weaver-defaults.toml")
)


class _WeaverProcess(Protocol):
    def start(self) -> _WeaverProcess: ...

    def close(self) -> None: ...


_TWeaver = TypeVar("_TWeaver", bound=_WeaverProcess)


@contextmanager
def _quiet_connection_retries() -> Generator[None, None, None]:
    """Silence urllib3's per-retry warning while weaver is coming up.

    Its ``/health`` is polled through a retrying session, so every refused
    connection before weaver binds its port is logged as a warning. That is
    the wait working, not a problem to report.
    """
    logger = logging.getLogger("urllib3.connectionpool")
    previous = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(previous)


@contextmanager
def _start_weaver(
    factory: Callable[[], _TWeaver],
) -> Generator[_TWeaver, None, None]:
    """Start weaver, retrying once if its fixed readiness window expires."""
    for attempt in range(2):
        weaver = factory()
        try:
            weaver.start()
        except TimeoutError:
            weaver.close()
            if attempt == 1:
                raise
            logger.warning("Weaver live-check startup timed out; retrying")
            continue

        try:
            yield weaver
        finally:
            weaver.close()
        return

    raise AssertionError("unreachable")


class SessionFactory(Protocol):
    """What ``conformance_session`` is, as a type.

    A wrapper package bakes in its own registry and reduction and registers
    itself under ``opentelemetry_conformance_runners``, so a directory naming
    it under ``runner:`` is opened with that wiring. See :mod:`._runners`.
    """

    def __call__(
        self,
        directory: Path | str,
        *,
        report_dir: Path | str | None = ...,
        data_file: Path | str | None = ...,
        variables: Mapping[str, str] | None = ...,
        weaver: WeaverSpec | None = ...,
        server: ServerSpec | None = ...,
        env: Mapping[str, str] | None = ...,
        build_data: Callable[[Path, PackageSpec], object] = ...,
        spec: PackageSpec | None = ...,
    ) -> AbstractContextManager[ConformanceSession]: ...


@dataclass(frozen=True)
class ScenarioReport:
    """What one scenario produced, and every way it fell short."""

    name: str
    failures: list[str]
    violations: list[str] = field(default_factory=list[str])
    report: LiveCheckReport | None = None
    stdout: str = ""
    stderr: str = ""


class ConformanceSession:
    """Runs a package's scenarios against a mock server and weaver."""

    def __init__(
        self,
        spec: PackageSpec,
        report_dir: Path,
        *,
        variables: Mapping[str, str],
        weaver: WeaverSpec,
        env: Mapping[str, str],
        data_file: Path,
        build_data: Callable[[Path, PackageSpec], object],
    ) -> None:
        if weaver.registry is None:
            raise SpecError(
                f"{spec.directory}: no weaver registry — declare one under "
                "weaver: in conformance.yaml, or pass a default"
            )
        self._spec = spec
        self._report_dir = report_dir
        self._variables = dict(variables)
        self._weaver = weaver
        self._registry = weaver.registry
        self._default_env = dict(env)
        self._data_file = data_file
        self._build_data = build_data
        self._ran: set[str] = set()

    @property
    def spec(self) -> PackageSpec:
        return self._spec

    def run(self, name: str) -> ScenarioReport:
        """Run one scenario under a fresh weaver live-check."""
        scenario = self._spec.scenarios.get(name)
        if scenario is None:
            raise KeyError(
                f"{name!r} is not declared in {self._spec.directory}; "
                f"declared: {sorted(self._spec.scenarios)}"
            )
        from opentelemetry.test.weaver_live_check import (  # noqa: PLC0415
            WeaverLiveCheck,
        )

        weaver_spec = self._weaver
        extra_args: list[str] = []
        if weaver_spec.config:
            extra_args += ["--config", self._resolve_path(weaver_spec.config)]
        if weaver_spec.advice_data:
            extra_args += [
                "--advice-data",
                self._resolve_path(weaver_spec.advice_data),
            ]

        def start_weaver() -> WeaverLiveCheck:
            return WeaverLiveCheck(
                inactivity_timeout=int(
                    timeout_seconds(*_WEAVER_INACTIVITY_TIMEOUT)
                ),
                registry=self._resolve_path(self._registry),
                policies_dir=self._resolve_path(weaver_spec.policies)
                if weaver_spec.policies
                else None,
                extra_args=extra_args,
            )

        with (
            _quiet_connection_retries(),
            _start_weaver(start_weaver) as weaver,
        ):
            completed = self._execute(scenario, weaver.otlp_endpoint)
            report = weaver.end(
                timeout=int(timeout_seconds(*_WEAVER_STOP_TIMEOUT))
            )

        # Before the checks, so a failing run still leaves a report to read.
        self._dump(name, report)
        self._ran.add(name)

        failures: list[str] = []
        if completed.returncode != 0:
            failures.append(
                f"{scenario.display_name}: scenario exited with "
                f"{completed.returncode}\n"
                f"--- stdout ---\n{completed.stdout}\n"
                f"--- stderr ---\n{completed.stderr}"
            )
        findings = check(scenario, report)
        failures += findings.failures
        return ScenarioReport(
            name=scenario.display_name,
            failures=failures,
            violations=findings.violations,
            report=report,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _resolve(self, value: str) -> str:
        return Template(value).safe_substitute(self._variables)

    def _resolve_path(self, value: str) -> str:
        """Resolve a declared path, relative ones against the package.

        A path in a config file reads as relative to that file, not to
        wherever the runner happens to be invoked from.
        """
        resolved = Path(self._resolve(value))
        # Through Path either way: substituting into `${ROOT}/model` otherwise
        # leaves whichever separator the config file was written with.
        if resolved.is_absolute():
            return str(resolved)
        return str(self._spec.directory / resolved)

    def _execute(
        self, scenario: ScenarioSpec, otlp_endpoint: str
    ) -> subprocess.CompletedProcess[str]:
        injected = {
            "OTEL_EXPORTER_OTLP_ENDPOINT": otlp_endpoint,
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
            "OTEL_METRIC_EXPORT_INTERVAL": str(METRIC_EXPORT_INTERVAL_MILLIS),
        }
        if scenario.index is not None:
            injected["OTEL_CONFORMANCE_SCENARIO_INDEX"] = str(scenario.index)
        return _run_command(
            scenario.run,
            cwd=scenario.directory,
            env=self._env(scenario.env, injected),
        )

    def _env(
        self, declared: Mapping[str, str], extra: Mapping[str, str]
    ) -> dict[str, str]:
        return build_env(
            self._default_env,
            self._spec.env,
            declared,
            injected={**self._variables, **extra},
        )

    def setup(self) -> subprocess.CompletedProcess[str] | None:
        """Run the package's ``setup`` command, if it declares one.

        No OTLP endpoint is in its environment, so whatever it emits stays
        invisible to the checks.
        """
        if self._spec.setup is None:
            return None
        completed = _run_command(
            self._spec.setup,
            cwd=self._spec.directory,
            env=self._env({}, {}),
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"setup command {self._spec.setup} failed with "
                f"{completed.returncode}\n"
                f"--- stdout ---\n{completed.stdout}\n"
                f"--- stderr ---\n{completed.stderr}"
            )
        return completed

    def _dump(self, name: str, report: LiveCheckReport) -> None:
        self._report_dir.mkdir(parents=True, exist_ok=True)
        (self._report_dir / f"{name}.json").write_text(
            # The report's own dict; weaver_live_check exposes no public
            # accessor for it yet.
            json.dumps(  # noqa: SLF001
                report._report,  # pyright: ignore[reportPrivateUsage]
                indent=2,
                sort_keys=True,
            )
        )

    def close(self) -> None:
        """Write the data file, if the run was complete and can produce one.

        A reduction only holds across a whole run, so a filtered one writes
        nothing rather than something partial. Failed scenarios still count as
        complete — the data file records what a run emitted either way. Only a
        run that *raised* is incomplete; :meth:`__exit__` skips this then.
        """
        if self._ran != set(self._spec.scenarios):
            return
        expected_reports = {f"{name}.json" for name in self._spec.scenarios}
        for report in self._report_dir.glob("*/*.json"):
            if report.name in expected_reports:
                report.unlink()
        data = self._build_data(self._report_dir, self._spec)
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        self._data_file.write_text(json.dumps(data, indent=2) + "\n")

    def __enter__(self) -> ConformanceSession:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        # A run that raised is partial; reducing it would overwrite the
        # committed data file with half a run.
        if exc_type is None:
            self.close()


def _run_command(
    command: tuple[str, ...], *, cwd: Path, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run a declared command, reporting its own failures as a failed run.

    A command that can't be started or that overruns is the same class of
    problem as one that exits non-zero — something the declaring package got
    wrong — so it comes back as a result rather than an exception.
    """
    limit = timeout_seconds(*_SCENARIO_TIMEOUT)
    try:
        return subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            env=dict(env),
            capture_output=True,
            text=True,
            timeout=limit,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        return _failed(
            command,
            f"did not finish within {limit}s",
            stdout=_text(expired.stdout),
            stderr=_text(expired.stderr),
        )
    except OSError as error:
        return _failed(command, str(error))


def _failed(
    command: tuple[str, ...],
    reason: str,
    *,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=list(command),
        returncode=1,
        stdout=stdout,
        stderr=f"{shlex.join(command)}: {reason}\n{stderr}",
    )


def _text(output: str | bytes | None) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


def _default_report_dir(directory: Path) -> Path:
    """Inside the conformance directory, so sibling implementations — which
    run the same scenario names — don't write over each other, and so a run
    lands in the same place however it was invoked.
    """
    return directory / DEFAULT_REPORT_DIR


@contextmanager
def conformance_session(
    directory: Path | str,
    *,
    report_dir: Path | str | None = None,
    data_file: Path | str | None = None,
    variables: Mapping[str, str] | None = None,
    weaver: WeaverSpec | None = None,
    server: ServerSpec | None = None,
    env: Mapping[str, str] | None = None,
    build_data: Callable[[Path, PackageSpec], object] = coverage,
    spec: PackageSpec | None = None,
) -> Generator[ConformanceSession, None, None]:
    """Open a session over the conformance directory at ``directory``.

    ``variables`` are substituted into the ``${...}`` references in the
    package's ``weaver`` and ``env`` blocks — that is how a registry
    provisioned at run time, or a server started by this session, reaches a
    committed YAML file.

    ``weaver``, ``server`` and ``env`` are defaults for what the package
    doesn't declare itself. Declare relative paths in ``weaver`` only from a
    package file — a default is resolved against each package directory in
    turn. A declared ``server`` runs for the session and publishes its base
    URL to the scenarios under its ``url_var``.

    A run produces two things, configured independently. ``report_dir`` holds
    one raw weaver report per scenario, ``<scenario>.json``, replaced each time
    that scenario runs and otherwise left alone. ``build_data``, given that
    directory and the spec after a complete run, returns the data to write to
    ``data_file``; it defaults to the attributes each declared span carried,
    plus the metrics and events the run produced.
    """
    check_weaver()
    spec = spec or load_spec(Path(directory))
    reports = (
        Path(report_dir)
        if report_dir is not None
        else _default_report_dir(Path(directory))
    )
    reports.mkdir(parents=True, exist_ok=True)

    with ExitStack() as stack:
        resolved = dict(variables or {})
        declared_server = spec.server.over(server or ServerSpec())
        if declared_server.run is not None:
            running = stack.enter_context(
                Server(
                    declared_server.run,
                    health_path=declared_server.health_path,
                )
            )
            resolved[declared_server.url_variable] = running.url

        session = ConformanceSession(
            spec,
            reports,
            variables=resolved,
            weaver=spec.weaver.over(weaver or WeaverSpec()).over(
                RUNNER_WEAVER_DEFAULTS
            ),
            env=env or {},
            data_file=Path(data_file)
            if data_file is not None
            else Path(directory) / DEFAULT_DATA_FILE,
            build_data=build_data,
        )
        session.setup()
        stack.enter_context(session)
        yield session
