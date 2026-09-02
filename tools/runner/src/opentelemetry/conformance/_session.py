# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The conformance session — a plain library, free of pytest.

It owns the package server, capture, and Weaver lifecycles so pytest and the CLI
use the same entry point. Scenario process failures and package live-check
findings are results; a broken runner still raises.
"""

from __future__ import annotations

import json
import logging
import shlex
import subprocess
from contextlib import AbstractContextManager, ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from string import Template
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Callable,
    Generator,
    Iterable,
    Mapping,
    Protocol,
    Sequence,
    TypeVar,
)

from ._checks import check_package_violations, check_scenario_telemetry
from ._coverage import coverage
from ._env import (
    METRIC_EXPORT_INTERVAL_MILLIS,
    SCENARIO_ACTION_VARIABLE,
    SCENARIO_ACTIONS_VARIABLE,
    SCENARIO_INDEX_VARIABLE,
    SCENARIO_PROTOCOL_VARIABLE,
    action_table_json,
    build_env,
    timeout_seconds,
)
from ._otlp_capture import (
    CapturedExport,
    CapturedWindow,
    OtlpCaptureProxy,
    UnexpectedExportsError,
)
from ._persistent import (
    DEFAULT_SETTLE_DELAY,
    DEFAULT_WINDOW_TIMEOUT,
    PERSISTENT_ENV,
    ActionState,
    PersistentController,
)
from ._registry import check_weaver
from ._report import (
    READINESS_REPORT,
    SCENARIO_REPORT_DIR,
    UNWINDOWED_REPORT,
    WEAVER_REPORT,
    write_capture,
    write_readiness,
    write_unwindowed,
    write_weaver,
)
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

_WEAVER_STOP_TIMEOUT = ("OTEL_CONFORMANCE_WEAVER_STOP_TIMEOUT", 120.0)
_CAPTURE_DRAIN_TIMEOUT = ("OTEL_CONFORMANCE_CAPTURE_DRAIN_TIMEOUT", 120.0)
_SCENARIO_TIMEOUT = ("OTEL_CONFORMANCE_SCENARIO_TIMEOUT", 600.0)
_SCENARIO_WINDOW_TIMEOUT = (
    "OTEL_CONFORMANCE_SCENARIO_WINDOW_TIMEOUT",
    DEFAULT_WINDOW_TIMEOUT,
)
_SCENARIO_SETTLE_DELAY = (
    "OTEL_CONFORMANCE_SCENARIO_SETTLE_DELAY",
    DEFAULT_SETTLE_DELAY,
)

# Both relative to the conformance directory. The reports are diagnostic;
# the data file is meant to be committed and diffed.
DEFAULT_REPORT_DIR = Path("output") / "reports"
DEFAULT_DATA_FILE = Path("data.json")

# Fallback only: a config declared by the caller or the package replaces it.
RUNNER_WEAVER_DEFAULTS = WeaverSpec(
    config=str(Path(__file__).parent / "weaver-defaults.toml")
)


class _WeaverProcess(Protocol):
    @property
    def otlp_endpoint(self) -> str: ...

    def start(self) -> _WeaverProcess: ...

    def end(self, timeout: int) -> LiveCheckReport: ...

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
    telemetry: CapturedWindow
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class PackageReport:
    """The scenario processes and aggregate Weaver result for one package."""

    scenarios: tuple[ScenarioReport, ...]
    failures: list[str]
    violations: list[str]
    report: LiveCheckReport


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
        self._scenario_reports: list[ScenarioReport] = []
        self._resources: ExitStack | None = None
        self._live_check: _WeaverProcess | None = None
        self._capture: OtlpCaptureProxy | None = None
        self._package_report: PackageReport | None = None
        self._finalize_error: BaseException | None = None
        self._ending = False

    @property
    def spec(self) -> PackageSpec:
        return self._spec

    def run(self, name: str) -> ScenarioReport:
        """Run one scenario in its own window of the package capture."""
        scenario = self._spec.scenarios.get(name)
        if scenario is None:
            raise KeyError(
                f"{name!r} is not declared in {self._spec.directory}; "
                f"declared: {sorted(self._spec.scenarios)}"
            )
        if self._ending or self._package_report is not None:
            raise RuntimeError(
                "The conformance package has already been finalized"
            )
        if not scenario.run_spec.one_shot:
            return self._run_persistent((scenario,))[0]
        self.start()
        assert self._capture is not None
        window = self._capture.open_window(name)
        try:
            completed = self._execute(scenario, self._capture.endpoint)
        finally:
            telemetry = self._capture.close_window(
                window,
                timeout=timeout_seconds(*_CAPTURE_DRAIN_TIMEOUT),
            )
        write_capture(self._report_dir, telemetry)
        self._ran.add(name)

        failures: list[str] = []
        if completed.returncode != 0:
            failures.append(
                f"{scenario.display_name}: scenario exited with "
                f"{completed.returncode}\n"
                f"--- stdout ---\n{completed.stdout}\n"
                f"--- stderr ---\n{completed.stderr}"
            )
        failures.extend(check_scenario_telemetry(scenario, telemetry))
        scenario_report = ScenarioReport(
            name=scenario.display_name,
            failures=failures,
            telemetry=telemetry,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        self._scenario_reports.append(scenario_report)
        return scenario_report

    def run_all(
        self, selected_names: Iterable[str] | None = None
    ) -> tuple[ScenarioReport, ...]:
        """Run the selected scenarios in declaration order by default."""
        names = (
            tuple(self._spec.scenarios)
            if selected_names is None
            else tuple(selected_names)
        )
        for name in names:
            if name not in self._spec.scenarios:
                raise KeyError(
                    f"{name!r} is not declared in {self._spec.directory}; "
                    f"declared: {sorted(self._spec.scenarios)}"
                )
        reports: list[ScenarioReport] = []
        index = 0
        while index < len(names):
            scenario = self._spec.scenarios[names[index]]
            if scenario.run_spec.one_shot:
                reports.append(self.run(names[index]))
                index += 1
                continue

            batch = [scenario]
            index += 1
            while index < len(names):
                candidate = self._spec.scenarios[names[index]]
                if (
                    candidate.run_spec != scenario.run_spec
                    or candidate.directory != scenario.directory
                    or candidate.env != scenario.env
                ):
                    break
                batch.append(candidate)
                index += 1
            reports.extend(self._run_persistent(batch))
        return tuple(reports)

    def _run_persistent(
        self, scenarios: Sequence[ScenarioSpec]
    ) -> tuple[ScenarioReport, ...]:
        self.start()
        assert self._capture is not None
        first = scenarios[0]
        protocol = first.run_spec.protocol
        assert protocol is not None
        injected = {
            "OTEL_EXPORTER_OTLP_ENDPOINT": self._capture.endpoint,
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
            # The command says what to start, not how it is driven. That
            # follows from the selected variant's role, so the runner tells
            # the process here rather than every package repeating a flag.
            SCENARIO_PROTOCOL_VARIABLE: protocol,
            **PERSISTENT_ENV,
        }
        # The runner owns the table, so a driver that starts a measured server
        # hands it on rather than rebuilding it: what answers the requests is
        # then the contract this package declared, custom or shared.
        if self._spec.action_table:
            injected[SCENARIO_ACTIONS_VARIABLE] = action_table_json(
                self._spec.action_table
            )
        controller = PersistentController(
            scenarios,
            capture=self._capture,
            cwd=first.directory,
            env=self._env(first.env, injected),
            timeout=timeout_seconds(*_SCENARIO_WINDOW_TIMEOUT),
            settle_delay=timeout_seconds(*_SCENARIO_SETTLE_DELAY),
            startup_timeout=timeout_seconds(*_SCENARIO_TIMEOUT),
        )
        reports: list[ScenarioReport] = []
        results = controller.run()
        write_readiness(self._report_dir, controller.readiness)
        for result in results:
            write_capture(self._report_dir, result.telemetry)
            if result.executed:
                self._ran.add(result.scenario.name)
            failures: list[str] = (
                [result.failure] if result.failure is not None else []
            )
            if result.state is ActionState.SEALED:
                failures.extend(
                    check_scenario_telemetry(result.scenario, result.telemetry)
                )
            report = ScenarioReport(
                name=result.scenario.display_name,
                failures=failures,
                telemetry=result.telemetry,
                stdout=result.stdout,
                stderr=result.stderr,
            )
            self._scenario_reports.append(report)
            reports.append(report)
        return tuple(reports)

    def start(self) -> None:
        """Start the package's single Weaver process and capture proxy."""
        if self._resources is not None:
            return
        if self._ending or self._package_report is not None:
            raise RuntimeError(
                "The conformance package has already been finalized"
            )

        resources = ExitStack()
        try:
            with _quiet_connection_retries():
                live_check = resources.enter_context(
                    _start_weaver(self._new_live_check)
                )
            capture = resources.enter_context(
                OtlpCaptureProxy(live_check.otlp_endpoint)
            )
        except BaseException:
            resources.close()
            raise
        self._resources = resources
        self._live_check = live_check
        self._capture = capture

    def _new_live_check(self) -> _WeaverProcess:
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
        return WeaverLiveCheck(
            inactivity_timeout=0,
            registry=self._resolve_path(self._registry),
            policies_dir=self._resolve_path(weaver_spec.policies)
            if weaver_spec.policies
            else None,
            extra_args=extra_args,
        )

    def finalize(self) -> PackageReport:
        """Stop package telemetry once and return its aggregate result.

        Finalizing is attempted once. A caller asking again for a report the
        session could not produce gets the failure that stopped it, rather
        than a second attempt at a package whose telemetry is already gone.
        Closing the session is not such a caller: :meth:`__exit__` releases
        what is left instead, so a failure reported where it happened is not
        raised a second time out of teardown.
        """
        if self._finalize_error is not None:
            raise self._finalize_error
        if self._package_report is not None:
            return self._package_report

        self.start()
        assert self._capture is not None
        assert self._live_check is not None
        self._ending = True
        failures: list[str] = []
        try:
            # Nothing may still be arriving when the quarantine is read: an
            # export the transport accepts after that read would never be
            # checked, and would land in no report.
            self._capture.close_ingress(
                timeout=timeout_seconds(*_CAPTURE_DRAIN_TIMEOUT)
            )
            try:
                self._capture.raise_for_quarantined()
            except UnexpectedExportsError as error:
                failures.append(str(error))
            quarantined = self._capture.quarantined_requests
            self._capture.close()
            report = self._live_check.end(
                timeout=int(timeout_seconds(*_WEAVER_STOP_TIMEOUT))
            )
        except BaseException as error:
            self._finalize_error = error
            raise
        finally:
            self._shutdown()

        findings = check_package_violations(
            self._spec,
            report,
            complete=self._ran == set(self._spec.scenarios),
        )
        package_report = PackageReport(
            scenarios=tuple(self._scenario_reports),
            failures=[*failures, *findings.failures],
            violations=findings.violations,
            report=report,
        )
        self._package_report = package_report
        try:
            self._dump_weaver(report)
            self._dump_unwindowed(quarantined)
            self._write_data()
        except BaseException as error:
            self._finalize_error = error
            raise
        return package_report

    def _shutdown(self) -> None:
        if self._resources is not None:
            self._resources.close()

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
        if not scenario.run_spec.one_shot:
            raise RuntimeError(
                f"scenario protocol {scenario.run_spec.protocol!r} is not "
                "a one-shot command"
            )
        injected = {
            "OTEL_EXPORTER_OTLP_ENDPOINT": otlp_endpoint,
            "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
            "OTEL_METRIC_EXPORT_INTERVAL": str(METRIC_EXPORT_INTERVAL_MILLIS),
        }
        if scenario.index is not None:
            injected[SCENARIO_INDEX_VARIABLE] = str(scenario.index)
        if scenario.action is not None:
            injected[SCENARIO_ACTION_VARIABLE] = json.dumps(
                scenario.action,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            )
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

    def _dump_weaver(self, report: LiveCheckReport) -> None:
        # WeaverLiveCheck exposes no public accessor for the report document.
        write_weaver(
            self._report_dir,
            report._report,  # pyright: ignore[reportPrivateUsage]  # noqa: SLF001
        )

    def _dump_unwindowed(self, captured: tuple[CapturedExport, ...]) -> None:
        path = self._report_dir / UNWINDOWED_REPORT
        if not captured:
            path.unlink(missing_ok=True)
            return
        write_unwindowed(
            self._report_dir,
            CapturedWindow(
                name="unwindowed",
                generation=0,
                exports=captured,
                spans=(),
                metric_names=(),
                event_names=(),
            ),
        )

    def _write_data(self) -> None:
        """Write the data file, if the run was complete and can produce one.

        A reduction only holds across a whole run, so a filtered one writes
        nothing rather than something partial. Failed scenarios still count as
        complete — the data file records what a run emitted either way. Only a
        run that *raised* is incomplete; :meth:`__exit__` skips this then.
        """
        if self._ran != set(self._spec.scenarios):
            return
        self._clean_stale_reports()
        data = self._build_data(self._report_dir, self._spec)
        self._data_file.parent.mkdir(parents=True, exist_ok=True)
        self._data_file.write_text(json.dumps(data, indent=2) + "\n")

    def _clean_stale_reports(self) -> None:
        """Remove files owned by the old and current report layouts."""

        scenarios = self._report_dir / SCENARIO_REPORT_DIR
        expected = {f"{name}.json" for name in self._spec.scenarios}
        if scenarios.is_dir():
            for path in scenarios.glob("*.json"):
                if path.name not in expected:
                    path.unlink()

        for path in self._report_dir.glob("*.json"):
            if path.name in {
                READINESS_REPORT.name,
                UNWINDOWED_REPORT.name,
                WEAVER_REPORT.name,
            }:
                continue
            if path.name in expected:
                path.unlink()

    def close(self) -> PackageReport:
        """Finalize the package through the context-manager close path."""
        return self.finalize()

    def __enter__(self) -> ConformanceSession:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None and self._finalize_error is None:
            self.finalize()
        else:
            self._ending = True
            self._shutdown()


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
    normalized captures under ``scenarios/`` and one aggregate
    ``weaver.json``. ``build_data``, given that directory and the spec after a
    complete run, returns the data to write to ``data_file``; it defaults to
    the attributes each declared span carried, plus the metrics and events the
    run produced.
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
                    env={
                        SCENARIO_ACTIONS_VARIABLE: action_table_json(
                            spec.action_table
                        )
                    }
                    if spec.action_table
                    else None,
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
