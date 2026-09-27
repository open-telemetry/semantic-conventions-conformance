# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The session around a run: commands, ``setup``, and the data file.

A command the package got wrong is a failed scenario, not an exception, so
one bad ``run:`` entry doesn't take the whole run down with it. Running a
scenario needs weaver, so the tests that don't exercise it drive the session
directly.
"""

from __future__ import annotations

import json
import os
import signal as signal_module
import subprocess
import sys
import time
from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal, cast

import pytest

from opentelemetry.conformance import (
    SpecError,
    WeaverSpec,
    _session,
    conformance_session,
    load_spec,
)
from opentelemetry.conformance._session import (
    ConformanceSession,
    _run_command,
    _start_weaver,
)

SPEC = """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  inference:
    run: python inference.py
  tool_calling:
    run: python tool_calling.py
"""


def test_a_command_that_runs(tmp_path: Path) -> None:
    completed = _run_command(
        (sys.executable, "-c", "print('hello')"), cwd=tmp_path, env={}
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "hello"


def test_a_command_that_does_not_exist(tmp_path: Path) -> None:
    completed = _run_command(
        ("definitely-not-a-command", "--flag"), cwd=tmp_path, env={}
    )

    assert completed.returncode == 1
    assert "definitely-not-a-command --flag" in completed.stderr


def test_a_command_that_overruns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OTEL_CONFORMANCE_SCENARIO_TIMEOUT", "0.5")

    completed = _run_command(
        (
            sys.executable,
            "-c",
            "import sys, time; print('started', flush=True); "
            "print('still running', file=sys.stderr, flush=True); "
            "time.sleep(30)",
        ),
        cwd=tmp_path,
        env={},
    )

    assert completed.returncode == 1
    assert completed.stdout.strip() == "started"
    assert "still running" in completed.stderr
    assert "did not finish within" in completed.stderr


def test_keyboard_interrupt_stops_command_before_reraising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Process:
        def wait(self, timeout: float) -> int:
            raise KeyboardInterrupt

    process = Process()
    stopped: list[Process] = []
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(_session, "_stop_process", stopped.append)
    monkeypatch.setattr(_session, "_command_job", lambda: nullcontext(None))

    with pytest.raises(KeyboardInterrupt):
        _run_command(("scenario",), cwd=tmp_path, env={})

    assert stopped == [process]


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no killable process group",
)
def test_a_command_that_overruns_stops_its_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A timed-out launcher must not leave its workload running."""
    monkeypatch.setenv("OTEL_CONFORMANCE_SCENARIO_TIMEOUT", "1")
    launched = tmp_path / "descendant-launched"
    ready = tmp_path / "descendant-ready"
    survived = tmp_path / "descendant-survived"
    child = (
        "import os, pathlib, sys, time\n"
        "parent_pid = int(sys.argv[1])\n"
        "pathlib.Path(sys.argv[2]).write_text('ready')\n"
        "while os.getppid() == parent_pid:\n"
        "    time.sleep(0.01)\n"
        "time.sleep(0.2)\n"
        "pathlib.Path(sys.argv[3]).write_text('alive')\n"
    )
    parent = (
        "import os, pathlib, subprocess, sys, time\n"
        "ready = pathlib.Path(sys.argv[3])\n"
        "child_args = [sys.executable, '-c', sys.argv[1], str(os.getpid())]\n"
        "child_args.extend([sys.argv[3], sys.argv[2]])\n"
        "subprocess.Popen(child_args)\n"
        "while not ready.exists():\n"
        "    time.sleep(0.01)\n"
        "pathlib.Path(sys.argv[4]).write_text('launched')\n"
        "time.sleep(30)\n"
    )

    real_popen = subprocess.Popen

    def popen_after_child_is_ready(
        *args: Any, **kwargs: Any
    ) -> subprocess.Popen[str]:
        process = real_popen(*args, **kwargs)
        if not _appears_within(launched, 10):
            process.kill()
            pytest.fail("descendant did not start")
        return cast("subprocess.Popen[str]", process)

    monkeypatch.setattr(subprocess, "Popen", popen_after_child_is_ready)
    completed = _run_command(
        (
            sys.executable,
            "-c",
            parent,
            child,
            str(survived),
            str(ready),
            str(launched),
        ),
        cwd=tmp_path,
        env=os.environ,
    )

    assert completed.returncode == 1
    assert launched.exists()
    assert not _appears_within(survived, 1)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals only")
def test_termination_signal_stops_a_scenario_group(tmp_path: Path) -> None:
    ready = tmp_path / "ready"
    survived = tmp_path / "survived"
    child = (
        "import pathlib, sys, time\n"
        "pathlib.Path(sys.argv[1]).write_text('ready')\n"
        "time.sleep(0.4)\n"
        "pathlib.Path(sys.argv[2]).write_text('alive')\n"
    )
    launcher = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], *sys.argv[2:]])\n"
        "time.sleep(30)\n"
    )
    runner = (
        "import pathlib, os, sys\n"
        "from opentelemetry.conformance._session import _run_command\n"
        "_run_command((sys.executable, '-c', sys.argv[1], "
        "sys.argv[2], sys.argv[3], sys.argv[4]), cwd=pathlib.Path.cwd(), env=os.environ)\n"
    )
    process = subprocess.Popen(
        (
            sys.executable,
            "-c",
            runner,
            launcher,
            child,
            str(ready),
            str(survived),
        ),
        cwd=tmp_path,
        env=os.environ,
        start_new_session=True,
    )
    try:
        assert _appears_within(ready, 10)
        os.killpg(process.pid, signal_module.SIGTERM)
        assert process.wait(timeout=10) == 128 + signal_module.SIGTERM
        assert not _appears_within(survived, 1)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal_module.SIGKILL)
            process.wait(timeout=10)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no killable process group",
)
def test_a_successful_launcher_does_not_leave_its_workload_running(
    tmp_path: Path,
) -> None:
    """A launcher exit must not leak its background workload."""
    ready = tmp_path / "descendant-ready"
    survived = tmp_path / "descendant-survived"
    child = (
        "import os, pathlib, sys, time\n"
        "parent_pid = int(sys.argv[1])\n"
        "pathlib.Path(sys.argv[2]).write_text('ready')\n"
        "while os.getppid() == parent_pid:\n"
        "    time.sleep(0.01)\n"
        "time.sleep(0.2)\n"
        "pathlib.Path(sys.argv[3]).write_text('alive')\n"
    )
    parent = (
        "import os, pathlib, subprocess, sys, time\n"
        "ready = pathlib.Path(sys.argv[2])\n"
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], "
        "str(os.getpid()), sys.argv[2], sys.argv[3]])\n"
        "while not ready.exists():\n"
        "    time.sleep(0.01)\n"
        "print('launcher done')\n"
    )

    completed = _run_command(
        (
            sys.executable,
            "-c",
            parent,
            child,
            str(ready),
            str(survived),
        ),
        cwd=tmp_path,
        env=os.environ,
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "launcher done"
    assert not _appears_within(survived, 1)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Job Object only")
def test_windows_launcher_does_not_leave_its_workload_running(
    tmp_path: Path,
) -> None:
    ready = tmp_path / "ready"
    survived = tmp_path / "survived"
    child = (
        "import pathlib, sys, time\n"
        "pathlib.Path(sys.argv[1]).write_text('ready')\n"
        "time.sleep(0.4)\n"
        "pathlib.Path(sys.argv[2]).write_text('alive')\n"
    )
    launcher = (
        "import pathlib, subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', sys.argv[1], *sys.argv[2:]])\n"
        "while not pathlib.Path(sys.argv[2]).exists():\n"
        "    time.sleep(0.01)\n"
    )
    completed = _run_command(
        (sys.executable, "-c", launcher, child, str(ready), str(survived)),
        cwd=tmp_path,
        env=os.environ,
    )

    assert completed.returncode == 0
    assert not _appears_within(survived, 1)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows has no killable process group",
)
def test_process_group_cleanup_does_not_require_a_live_leader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The group can outlive the launcher used to create it."""

    class Process:
        pid = 123
        killed = False

        def kill(self) -> None:
            self.killed = True

    def missing_leader(_pid: int) -> int:
        raise ProcessLookupError

    groups: list[tuple[int, signal_module.Signals]] = []
    # Guard against reintroducing a pgid lookup after the leader has exited.
    monkeypatch.setattr(os, "getpgid", missing_leader)
    monkeypatch.setattr(
        os,
        "killpg",
        lambda pgid, sig: groups.append((pgid, sig)),
    )
    process = Process()

    _session._kill_process_group(cast("subprocess.Popen[str]", process))

    assert groups == [(process.pid, signal_module.SIGKILL)]
    assert not process.killed


def test_timeout_cleanup_wait_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Process:
        def __init__(self) -> None:
            self.pid = 123
            self.waits: list[float] = []

        def wait(self, timeout: float) -> int:
            self.waits.append(timeout)
            raise subprocess.TimeoutExpired("scenario", timeout)

    process = Process()
    stopped: list[Process] = []
    monkeypatch.setattr(_session, "_kill_process_group", stopped.append)
    monkeypatch.setattr(_session, "_COMMAND_CLEANUP_TIMEOUT_SECONDS", 0.1)

    _session._stop_process(cast("subprocess.Popen[str]", process))

    assert stopped == [process]
    assert process.waits == [0.1]


def test_captured_output_does_not_move_the_writer_offset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "capture"
    with path.open("w+b") as capture:
        capture.write(b"captured output")
        capture.flush()
        capture.seek(3)

        output = _session._captured_text(capture, "utf-8")

        assert output == "captured output"
        assert capture.tell() == 3


def test_captured_output_replaces_invalid_bytes(tmp_path: Path) -> None:
    path = tmp_path / "capture"
    with path.open("w+b") as capture:
        capture.write(b"before \xff after")
        capture.flush()

        output = _session._captured_text(capture, "utf-8")

    assert output == "before \N{REPLACEMENT CHARACTER} after"


def test_timeout_does_not_wait_for_inherited_output_handles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A surviving descendant must not hold timeout cleanup open."""
    monkeypatch.setenv("OTEL_CONFORMANCE_SCENARIO_TIMEOUT", "0.1")
    ready = tmp_path / "descendant-ready"
    child_pid = tmp_path / "descendant-pid"
    child = (
        "import pathlib, sys, time\n"
        "print('child ready', flush=True)\n"
        "pathlib.Path(sys.argv[1]).write_text('ready')\n"
        "time.sleep(10)\n"
    )
    parent = (
        "import pathlib, subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', sys.argv[1], "
        "sys.argv[2]])\n"
        "pathlib.Path(sys.argv[3]).write_text(str(child.pid))\n"
        "time.sleep(30)\n"
    )
    real_popen = subprocess.Popen
    ready_at: list[float] = []

    def popen_after_descendant_is_ready(
        *args: Any, **kwargs: Any
    ) -> subprocess.Popen[str]:
        process = real_popen(*args, **kwargs)
        deadline = time.monotonic() + 10
        while not ready.exists():
            if time.monotonic() >= deadline:
                process.kill()
                pytest.fail("descendant did not start")
            time.sleep(0.01)
        ready_at.append(time.monotonic())
        return cast("subprocess.Popen[str]", process)

    monkeypatch.setattr(subprocess, "Popen", popen_after_descendant_is_ready)
    monkeypatch.setattr(
        _session, "_kill_process_group", lambda process: process.kill()
    )
    monkeypatch.setattr(_session, "_COMMAND_CLEANUP_TIMEOUT_SECONDS", 0.5)
    try:
        completed = _run_command(
            (
                sys.executable,
                "-c",
                parent,
                child,
                str(ready),
                str(child_pid),
            ),
            cwd=tmp_path,
            env=os.environ,
        )
    finally:
        if child_pid.exists():
            try:
                os.kill(int(child_pid.read_text()), signal_module.SIGTERM)
            except OSError:
                pass

    assert time.monotonic() - ready_at[0] < 2
    assert completed.returncode == 1
    assert "child ready" in completed.stdout
    assert "did not finish within" in completed.stderr


def _appears_within(path: Path, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.01)
    return path.exists()


def test_weaver_startup_retries_after_a_timeout() -> None:
    attempts: list[_FakeWeaver] = []

    def factory() -> _FakeWeaver:
        weaver = _FakeWeaver(fail_start=not attempts)
        attempts.append(weaver)
        return weaver

    with _start_weaver(factory) as weaver:
        assert weaver is attempts[1]

    assert [attempt.starts for attempt in attempts] == [1, 1]
    assert [attempt.closes for attempt in attempts] == [1, 1]


def test_weaver_startup_stops_after_the_retry() -> None:
    attempts: list[_FakeWeaver] = []

    def factory() -> _FakeWeaver:
        weaver = _FakeWeaver(fail_start=True)
        attempts.append(weaver)
        return weaver

    with pytest.raises(TimeoutError), _start_weaver(factory):
        pass

    assert len(attempts) == 2
    assert [attempt.closes for attempt in attempts] == [1, 1]


class _FakeWeaver:
    def __init__(self, *, fail_start: bool) -> None:
        self.fail_start = fail_start
        self.starts = 0
        self.closes = 0

    def start(self) -> _FakeWeaver:
        self.starts += 1
        if self.fail_start:
            raise TimeoutError
        return self

    def close(self) -> None:
        self.closes += 1


def test_the_scenario_gets_exactly_the_environment_it_was_given(
    tmp_path: Path,
) -> None:
    completed = _run_command(
        (sys.executable, "-c", "import os; print(os.environ['DECLARED'])"),
        cwd=tmp_path,
        env={"DECLARED": "value"},
    )

    assert completed.returncode == 0
    assert completed.stdout.strip() == "value"


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    (tmp_path / "conformance.yaml").write_text(SPEC)
    return tmp_path


def session(
    directory: Path,
    data_file: Path,
    setup: tuple[str, ...] | None = None,
    report_dir: Path | None = None,
    otlp_protocol: Literal["grpc", "http/protobuf"] = "grpc",
) -> ConformanceSession:
    return ConformanceSession(
        replace(
            load_spec(directory),
            setup=setup,
            otlp_protocol=otlp_protocol,
        ),
        report_dir if report_dir is not None else directory / "reports",
        variables={"ROOT": str(directory)},
        weaver=WeaverSpec(registry="model"),
        env={},
        data_file=data_file,
        build_data=lambda reports, spec: {
            "library": spec.instrumented_library,
            "reports": reports.name,
        },
    )


@pytest.mark.parametrize("index", [None, 3])
@pytest.mark.parametrize(
    ("otlp_protocol", "otlp_endpoint"),
    [
        ("grpc", "http://localhost:4317"),
        ("http/protobuf", "http://127.0.0.1:12345"),
    ],
)
def test_scenario_uses_only_generic_otlp_configuration(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    otlp_protocol: Literal["grpc", "http/protobuf"],
    otlp_endpoint: str,
    index: int | None,
) -> None:
    captured: dict[str, str] = {}

    def run(
        command: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        captured.update(env)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_session, "_run_command", run)
    for signal in ("TRACES", "METRICS", "LOGS"):
        monkeypatch.setenv(
            f"OTEL_EXPORTER_OTLP_{signal}_ENDPOINT",
            "http://example.com:4317",
        )
        monkeypatch.setenv(
            f"OTEL_EXPORTER_OTLP_{signal}_PROTOCOL",
            "ambient",
        )
    opened = session(
        directory,
        tmp_path / "data.json",
        otlp_protocol=otlp_protocol,
    )

    opened._execute(  # noqa: SLF001
        replace(opened.spec.scenarios["inference"], index=index),
        otlp_endpoint,
    )

    assert captured["OTEL_EXPORTER_OTLP_ENDPOINT"] == otlp_endpoint
    assert captured["OTEL_EXPORTER_OTLP_PROTOCOL"] == otlp_protocol
    if index is not None:
        assert captured["OTEL_CONFORMANCE_SCENARIO_INDEX"] == str(index)
    for signal in ("TRACES", "METRICS", "LOGS"):
        assert f"OTEL_EXPORTER_OTLP_{signal}_ENDPOINT" not in captured
        assert f"OTEL_EXPORTER_OTLP_{signal}_PROTOCOL" not in captured


def test_a_complete_run_writes_the_data_file(
    directory: Path, tmp_path: Path
) -> None:
    data_file = tmp_path / "nested" / "data.json"
    opened = session(directory, data_file)
    opened._ran.update(["inference", "tool_calling"])

    opened.close()

    assert json.loads(data_file.read_text()) == {
        "library": "demo",
        "reports": "reports",
    }


def test_a_filtered_run_leaves_the_data_file_alone(
    directory: Path, tmp_path: Path
) -> None:
    """A reduction over the reports only holds across a whole run."""
    data_file = tmp_path / "data.json"
    opened = session(directory, data_file)
    opened._ran.add("inference")

    opened.close()

    assert not data_file.exists()


def test_a_run_that_raised_leaves_the_data_file_alone(
    directory: Path, tmp_path: Path
) -> None:
    """Its reports cover part of a run; reducing them would commit a half-run."""
    data_file = tmp_path / "data.json"

    with pytest.raises(RuntimeError, match="harness"):
        with session(directory, data_file) as opened:
            opened._ran.update(["inference", "tool_calling"])
            raise RuntimeError("the harness broke")

    assert not data_file.exists()


def test_a_run_whose_scenarios_failed_still_writes_the_data_file(
    directory: Path, tmp_path: Path
) -> None:
    """A violation is the result, not an error — the run still reduces."""
    data_file = tmp_path / "data.json"

    with session(directory, data_file) as opened:
        opened._ran.update(["inference", "tool_calling"])

    assert json.loads(data_file.read_text()) == {
        "library": "demo",
        "reports": "reports",
    }


def test_setup_is_optional(directory: Path, tmp_path: Path) -> None:
    assert session(directory, tmp_path / "data.json").setup() is None


def test_setup_runs_the_declared_command(
    directory: Path, tmp_path: Path
) -> None:
    completed = session(
        directory,
        tmp_path / "data.json",
        setup=(sys.executable, "-c", "print('prepared')"),
    ).setup()

    assert completed is not None
    assert completed.stdout.strip() == "prepared"


def test_a_failing_setup_stops_the_session(
    directory: Path, tmp_path: Path
) -> None:
    opened = session(
        directory,
        tmp_path / "data.json",
        setup=(sys.executable, "-c", "raise SystemExit(3)"),
    )

    with pytest.raises(RuntimeError, match="setup command"):
        opened.setup()


def test_declared_paths_resolve_against_the_package(
    directory: Path, tmp_path: Path
) -> None:
    """A path in a config file reads as relative to that file."""
    opened = session(directory, tmp_path / "data.json")

    # Use tmp_path's anchor so Path.is_absolute() recognizes this on Windows;
    # a rooted path without a drive is not absolute to pathlib.
    absolute = str(Path(tmp_path.anchor) / "absolute" / "model")

    assert opened._resolve_path("model") == str(directory / "model")
    assert opened._resolve_path("${ROOT}/model") == str(directory / "model")
    assert opened._resolve_path(absolute) == absolute


def test_contract_index_is_injected_into_the_scenario_process(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def run(
        command: tuple[str, ...], *, cwd: Path, env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        del command, cwd
        captured.update(env)
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(_session, "_run_command", run)
    opened = session(directory, tmp_path / "data.json")
    scenario = replace(
        opened.spec.scenarios["inference"],
        index=3,
    )

    opened._execute(scenario, "http://collector")

    assert captured["OTEL_CONFORMANCE_SCENARIO_INDEX"] == "3"


def test_a_missing_registry_is_a_spec_error(
    directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Opening a session looks for weaver before it reads the registry, and
    # this is the one test here that goes in through the front door.
    monkeypatch.setattr(_session, "check_weaver", lambda: None)
    with pytest.raises(SpecError, match="no weaver registry"):
        with conformance_session(directory):
            pass


def test_a_preloaded_spec_is_not_read_again(
    directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = load_spec(directory)
    monkeypatch.setattr(_session, "check_weaver", lambda: None)
    monkeypatch.setattr(
        _session,
        "load_spec",
        lambda path: pytest.fail(f"reloaded {path}"),
    )

    with conformance_session(
        directory,
        data_file=tmp_path / "data.json",
        weaver=WeaverSpec(registry="model"),
        spec=spec,
    ) as opened:
        assert opened.spec is spec


def test_a_scenario_replaces_only_its_own_report(
    directory: Path, tmp_path: Path
) -> None:
    """Running one scenario mustn't discard what the others last reported."""
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "inference.json").write_text('{"run": "first"}')
    (reports / "tool_calling.json").write_text('{"run": "first"}')

    opened = session(directory, tmp_path / "data.json", report_dir=reports)
    opened._dump("inference", SimpleNamespace(_report={"run": "second"}))

    assert json.loads((reports / "inference.json").read_text()) == {
        "run": "second"
    }
    assert json.loads((reports / "tool_calling.json").read_text()) == {
        "run": "first"
    }


def test_a_complete_run_removes_only_immediate_nested_duplicates(
    directory: Path, tmp_path: Path
) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "inference.json").write_text("{}")
    (reports / "tool_calling.json").write_text("{}")
    unrelated = reports / "metadata.json"
    unrelated.write_text("{}")
    nested = reports / "old"
    nested.mkdir()
    nested_stale = nested / "inference.json"
    nested_stale.write_text("{}")
    nested_unrelated = nested / "metadata.json"
    nested_unrelated.write_text("{}")
    deep = nested / "unrelated"
    deep.mkdir()
    deep_duplicate = deep / "inference.json"
    deep_duplicate.write_text("{}")
    opened = session(directory, tmp_path / "data.json", report_dir=reports)
    opened._ran.update(opened.spec.scenarios)

    opened.close()

    assert not nested_stale.exists()
    assert unrelated.exists()
    assert nested_unrelated.exists()
    assert deep_duplicate.exists()


def test_reports_default_to_inside_the_scenario_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sibling implementations run the same scenario names; keep them apart."""
    monkeypatch.chdir(tmp_path)
    scenarios = Path("gen-ai/python/openai/opentelemetry")

    assert (
        _session._default_report_dir(scenarios)
        == scenarios / _session.DEFAULT_REPORT_DIR
    )


def test_the_default_report_dir_does_not_move_with_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pytest and a shell pick different ones; the reports land in one place."""
    scenarios = tmp_path / "gen-ai" / "python" / "openai" / "opentelemetry"
    scenarios.mkdir(parents=True)
    here = tmp_path / "here"
    here.mkdir()

    monkeypatch.chdir(tmp_path)
    from_root = _session._default_report_dir(scenarios)
    monkeypatch.chdir(here)

    assert _session._default_report_dir(scenarios) == from_root
