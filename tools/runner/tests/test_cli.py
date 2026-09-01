# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance`` and the session factory a repo swaps in.

The factory is how a repo bakes in its own registry and mock server — see
``opentelemetry.test_util_genai.conformance`` — so the CLI has to accept one
and hand it everything it parsed.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from inspect import signature
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

import pytest

from opentelemetry.conformance import (
    PackageSpec,
    ScenarioReport,
    ServerSpec,
    WeaverSpec,
    conformance_session,
    coverage,
    load_spec,
)
from opentelemetry.conformance._cli import _DataCommandError, main
from opentelemetry.conformance._session import ConformanceSession

# Emits {"library": …, "instrumentation": …, "reports": …} from the three
# inputs and a glob.
DATA_COMMAND = (
    r"""printf '{"library": "%s", "instrumentation": "%s", "reports": %s}' """
    r'"$2" "$3" "$(ls "$1"/*.json | wc -l)"'
)
POSIX_SHELL_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="--data-command has a documented POSIX sh contract",
)

SPEC = """
instrumented_library: demo
instrumentation_library: demo-instrumentation
runner_config:
  sample: value
scenarios:
  inference:
    run: python inference.py
  tool_calling:
    run: python tool_calling.py
"""


class FakeSession:
    """Records what ran; never starts weaver or a server."""

    def __init__(
        self, spec: PackageSpec, failing: set[str], violating: set[str]
    ) -> None:
        self.spec = spec
        self.ran: list[str] = []
        self._failing = failing
        self._violating = violating

    def run(self, name: str) -> ScenarioReport:
        self.ran.append(name)
        return ScenarioReport(
            name=name,
            failures=[f"{name}: nope"] if name in self._failing else [],
            violations=[f"{name} is missing server.address, id=some_advice"]
            if name in self._violating
            else [],
        )


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    (tmp_path / "conformance.yaml").write_text(SPEC)
    return tmp_path


def factory(
    sessions: list[FakeSession],
    calls: list[dict[str, Any]],
    failing: set[str] | None = None,
    *,
    violating: set[str] | None = None,
    reduce_on_close: bool = False,
) -> Callable[..., Any]:
    @contextmanager
    def open_session(
        directory: Path | str, **kwargs: Any
    ) -> Iterator[FakeSession]:
        calls.append({"directory": directory, **kwargs})
        session = FakeSession(
            load_spec(Path(directory)), failing or set(), violating or set()
        )
        sessions.append(session)
        yield session
        # What the real session does on the way out of the block.
        if reduce_on_close and "build_data" in kwargs:
            kwargs["build_data"](Path("reports"), session.spec)

    return open_session


def test_runs_every_declared_scenario(directory: Path) -> None:
    sessions: list[FakeSession] = []
    calls: list[dict[str, Any]] = []

    assert main([str(directory)], session=factory(sessions, calls)) == 0
    assert sessions[0].ran == ["inference", "tool_calling"]


def test_scenario_filter(directory: Path) -> None:
    sessions: list[FakeSession] = []

    assert (
        main(
            [str(directory), "--scenario", "tool_calling"],
            session=factory(sessions, []),
        )
        == 0
    )
    assert sessions[0].ran == ["tool_calling"]


def test_failures_become_a_non_zero_exit(directory: Path) -> None:
    assert (
        main(
            [str(directory)],
            session=factory([], [], failing={"inference"}),
        )
        == 1
    )


def test_the_header_names_the_declared_libraries(
    directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A package's directory is not what it measured; its spec says that."""
    assert main([str(directory)], session=factory([], [])) == 0

    assert (
        "==== instrumented: demo, instrumentation: demo-instrumentation, "
        f"package: {directory.name}" in capsys.readouterr().out
    )


def test_report_only_warns_about_violations(
    directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [str(directory), "--report-only"],
            session=factory([], [], violating={"inference"}),
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "scenario: inference, status: WARN" in out
    assert "Violations:" in out
    assert "is missing server.address" in out


def test_colour_follows_the_environment(
    directory: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    main([str(directory)], session=factory([], [], failing={"inference"}))
    assert "\033[31m✖ scenario: inference, status: FAIL" in (
        capsys.readouterr().out
    )

    monkeypatch.setenv("NO_COLOR", "1")
    main([str(directory)], session=factory([], [], failing={"inference"}))
    assert "\033[" not in capsys.readouterr().out


def test_report_only_still_fails_on_a_broken_scenario(directory: Path) -> None:
    assert (
        main(
            [str(directory), "--report-only"],
            session=factory([], [], failing={"inference"}),
        )
        == 1
    )


def test_options_reach_the_session(directory: Path, tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    main(
        [
            str(directory),
            "--registry",
            "model",
            "--policies",
            "policies",
            "--server",
            "serve --port ${PORT}",
            "--server-url-var",
            "BASE_URL",
            "--env",
            "OPENAI_API_KEY=placeholder",
            "--var",
            "REGISTRY_ROOT=/tmp/registry",
        ],
        session=factory([], calls),
    )

    (call,) = calls
    spec: PackageSpec = call["spec"]
    weaver: WeaverSpec = call["weaver"]
    server: ServerSpec = call["server"]
    env: Mapping[str, str] = call["env"]

    # A path on the command line is relative to the caller's shell, so it is
    # absolute by the time the session sees it.
    assert weaver.registry is not None
    assert Path(weaver.registry).is_absolute()
    assert Path(weaver.registry).name == "model"
    assert server.run == ("serve", "--port", "${PORT}")
    assert server.url_var == "BASE_URL"
    assert env == {"OPENAI_API_KEY": "placeholder"}
    assert call["variables"] == {"REGISTRY_ROOT": "/tmp/registry"}
    assert spec.directory == directory
    assert spec.runner_config == {"sample": "value"}


def test_the_session_factory_chooses_the_reduction(directory: Path) -> None:
    """The CLI passes none, so a wrapping factory's own default survives.

    Passing the generic reduction here would silently override the one a
    conventions-aware wrapper knows how to do.
    """
    calls: list[dict[str, Any]] = []

    main([str(directory)], session=factory([], calls))

    assert "build_data" not in calls[0]
    # …and the plain session still defaults to it.
    assert (
        signature(conformance_session).parameters["build_data"].default
        is coverage
    )


def test_capture_traces_omitted_unless_requested(directory: Path) -> None:
    """Capture is newer than some third-party ``SessionFactory``s, so it must
    not reach one that was never updated to accept it.
    """
    calls: list[dict[str, Any]] = []

    main([str(directory)], session=factory([], calls))

    assert "capture_traces" not in calls[0]


def test_capture_traces_reaches_the_session(directory: Path) -> None:
    calls: list[dict[str, Any]] = []

    main([str(directory), "--capture-traces"], session=factory([], calls))

    assert calls[0]["capture_traces"] is True


@POSIX_SHELL_ONLY
def test_data_command_runs_in_a_shell(directory: Path, tmp_path: Path) -> None:
    """It is handed a directory, so it has to be able to glob it.

    The report directory arrives as ``$1``, the library as ``$2`` and the
    instrumentation as ``$3``, which is what lets a one-liner stand in for a
    reduction script.
    """
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "inference.json").write_text("{}")
    (reports / "tool_calling.json").write_text("{}")

    calls: list[dict[str, Any]] = []
    main(
        [str(directory), "--data-command", DATA_COMMAND],
        session=factory([], calls),
    )

    assert calls[0]["build_data"](reports, load_spec(directory)) == {
        "library": "demo",
        "instrumentation": "demo-instrumentation",
        "reports": 2,
    }


@POSIX_SHELL_ONLY
@pytest.mark.parametrize(
    ("command", "message"),
    [
        pytest.param("exit 2", "exited with 2", id="non-zero-exit"),
        pytest.param("echo not json", "did not print JSON", id="not-json"),
    ],
)
def test_a_broken_data_command_is_reported(
    directory: Path, command: str, message: str
) -> None:
    """One error the run made, not a traceback out of the session's close."""
    calls: list[dict[str, Any]] = []
    main(
        [str(directory), "--data-command", command],
        session=factory([], calls),
    )

    with pytest.raises(_DataCommandError, match=message):
        calls[0]["build_data"](Path("reports"), load_spec(directory))


@POSIX_SHELL_ONLY
def test_a_broken_data_command_fails_the_run(
    directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """It runs when the session closes, after every scenario has reported."""
    calls: list[dict[str, Any]] = []

    exit_code = main(
        [str(directory), "--data-command", "exit 2"],
        session=factory([], calls, reduce_on_close=True),
    )

    assert exit_code == 1
    printed = capsys.readouterr().out
    assert "scenario: inference, status: ok" in printed
    assert "FAIL --data-command exited with 2" in printed


def test_undeclared_scenario_is_an_error(directory: Path) -> None:
    """``run`` raising KeyError is the session's contract, not a silent skip."""
    session = ConformanceSession(
        load_spec(directory),
        Path("reports"),
        variables={},
        weaver=WeaverSpec(registry="model"),
        env={},
        data_file=Path("data.json"),
        build_data=lambda _reports, _spec: {},
    )

    with pytest.raises(KeyError, match="nonexistent"):
        session.run("nonexistent")


def test_bad_key_value_option(directory: Path) -> None:
    with pytest.raises(SystemExit):
        main([str(directory), "--env", "NOEQUALS"], session=factory([], []))
