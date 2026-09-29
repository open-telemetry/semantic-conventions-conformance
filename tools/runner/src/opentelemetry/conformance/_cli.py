# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance <dir> [options]``.

Everything a session takes is available here, so a repo can wire conformance
up without writing Python: the registry to validate against, defaults for the
environment, a server to run, and a command to reduce the reports afterwards.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Callable

from ._registry import WeaverNotInstalledError
from ._runners import resolve as resolve_runner
from ._session import (
    DEFAULT_DATA_FILE,
    DEFAULT_REPORT_DIR,
    SessionFactory,
)
from ._spec import PackageSpec, ServerSpec, SpecError, WeaverSpec, load_spec


class _DataCommandError(RuntimeError):
    """``--data-command`` failed or printed something that isn't JSON."""


# NO_COLOR/FORCE_COLOR conventions: https://no-color.org
def _colour_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()


_CODES = {
    "green": "32",
    "red": "31",
    "yellow": "33",
    "dim": "2",
    "bold": "1",
}


def _paint(text: str, colour: str) -> str:
    if not _colour_enabled():
        return text
    return f"\033[{_CODES[colour]}m{text}\033[0m"


# Colour, mark, and an ASCII stand-in for a console that cannot encode it.
_OK = ("green", "\u2714 ", "+ ")
_WARN = ("yellow", "\u25b2 ", "! ")
_FAIL = ("red", "\u2716 ", "x ")


def _symbol(mark: tuple[str, str, str]) -> str:
    """The mark, or its stand-in where stdout is a legacy codepage.

    Checked per call rather than once: what stdout is depends on how the CLI
    was started, not on when this module happened to be imported.
    """
    _, symbol, plain = mark
    try:
        symbol.encode(sys.stdout.encoding or "ascii")
    except (LookupError, UnicodeEncodeError):
        return plain
    return symbol


def _status(mark: tuple[str, str, str], line: str) -> None:
    print(_paint(f"{_symbol(mark)}{line}", mark[0]))


def _findings(
    mark: tuple[str, str, str], title: str, texts: list[str]
) -> None:
    """A titled list under a scenario; anything multi-line reads as output."""
    if not texts:
        return
    print(_paint(f"{_symbol(mark)}{title}:", mark[0]))
    for text in texts:
        first, _, rest = text.partition("\n")
        print(f"  - {first}")
        if rest:
            print(_paint(rest, "dim"))


def _key_value(argument: str) -> tuple[str, str]:
    key, separator, value = argument.partition("=")
    if not separator or not key:
        raise argparse.ArgumentTypeError(
            f"expected KEY=VALUE, got {argument!r}"
        )
    return key, value


def _absolute(value: str | None) -> str | None:
    """A path given on the command line is relative to the caller's cwd.

    Only paths declared inside a package file are relative to that file.
    """
    return None if value is None else str(Path(value).absolute())


def _parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Run a package's conformance scenarios.",
    )
    parser.add_argument(
        "directory", type=Path, help="the package's conformance directory"
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        metavar="NAME",
        help="run only this scenario (repeatable); the data file is not "
        "written, since a reduction over the reports only holds for a whole "
        "run",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        metavar="DIR",
        help=(
            "one raw weaver report per scenario (default "
            f"<DIRECTORY>/{DEFAULT_REPORT_DIR})"
        ),
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        metavar="PATH",
        help="where the reduction over a complete run is written — the "
        "built-in coverage, or --data-command's output "
        f"(default <DIRECTORY>/{DEFAULT_DATA_FILE})",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="report semconv violations as warnings instead of failures; "
        "a scenario that crashed or missed what it declared still fails",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="log warnings only; by default the run says what it is doing "
        "(fetching a registry, an environment variable it took from the "
        "process environment)",
    )

    weaver = parser.add_argument_group(
        "registry", "defaults for what the package doesn't declare"
    )
    weaver.add_argument(
        "--registry",
        metavar="PATH",
        help="the semantic-convention registry to validate against, and to "
        "reduce the run's coverage against",
    )
    weaver.add_argument(
        "--policies",
        metavar="PATH",
        help="directory of weaver advice .rego policies, run on top of the "
        "registry's own checks",
    )
    weaver.add_argument(
        "--advice-data",
        metavar="GLOB",
        help="extra JSON/YAML loaded into the policies' rego data",
    )
    weaver.add_argument(
        "--weaver-config",
        metavar="PATH",
        help="weaver.toml for the live-check; replaces the runner's default, "
        "which filters out findings on SDK resource attributes",
    )

    environment = parser.add_argument_group("environment")
    environment.add_argument(
        "--env",
        action="append",
        default=[],
        type=_key_value,
        metavar="KEY=VALUE",
        help="default environment variable for the scenarios (repeatable)",
    )
    environment.add_argument(
        "--var",
        action="append",
        default=[],
        type=_key_value,
        metavar="KEY=VALUE",
        help="value for a ${KEY} reference in the package file (repeatable)",
    )

    server = parser.add_argument_group(
        "server", "a server to run for the session"
    )
    server.add_argument(
        "--server",
        metavar="COMMAND",
        help="command to run; it is told its port through ${PORT} and "
        "inherits this environment",
    )
    server.add_argument(
        "--server-health",
        metavar="PATH",
        help="path polled until it answers 200 (default /health)",
    )
    server.add_argument(
        "--server-url-var",
        metavar="NAME",
        help="variable the base URL reaches the scenarios as "
        "(default MOCK_SERVER_URL)",
    )

    parser.add_argument(
        "--data-command",
        metavar="COMMAND",
        help="reduce a complete run into the data file with this shell "
        'command instead of the built-in coverage: "$1" is the report '
        'directory, "$2" the instrumented library, "$3" the instrumentation '
        "library, and its stdout is the data",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    session: SessionFactory | None = None,
    prog: str = "otel-conformance",
) -> int:
    """Run a directory's scenarios.

    ``session`` pins which wrapper opens it, which is how a wrapper's own
    console script reuses this CLI. Left out, the directory's ``runner:`` key
    decides — so ``otel-conformance`` works for any directory whose wrapper is
    installed.

    ``prog`` is the command name the usage line reports. A domain wrapper
    passes its own console-script name, so ``--help`` names the command that
    was run.
    """
    args = _parser(prog).parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        spec = load_spec(Path(args.directory))
        factory = session or resolve_runner(args.directory, spec=spec)
    except SpecError as error:
        _status(_FAIL, f"FAIL {error}")
        return 1

    def run_data_command(report_dir: Path, spec: PackageSpec) -> object:
        # Through a shell, so the command can glob the directory it is handed.
        completed = subprocess.run(  # noqa: S603
            [
                "sh",
                "-c",
                args.data_command,
                "sh",
                str(report_dir),
                spec.instrumented_library,
                spec.instrumentation_library,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise _DataCommandError(
                f"--data-command exited with {completed.returncode}\n"
                f"--- stdout ---\n{completed.stdout}\n"
                f"--- stderr ---\n{completed.stderr}"
            )
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise _DataCommandError(
                f"--data-command did not print JSON: {error}\n"
                f"--- stdout ---\n{completed.stdout}"
            ) from error

    # The reduction runs on session close, so a broken --data-command surfaces
    # here, after every scenario has already been reported.
    try:
        failed = _run(args, factory, spec, run_data_command)
    except (_DataCommandError, SpecError, WeaverNotInstalledError) as error:
        failed = True
        _status(_FAIL, f"FAIL {error}")
    return 1 if failed else 0


def _run(
    args: argparse.Namespace,
    session: SessionFactory,
    spec: PackageSpec,
    run_data_command: Callable[[Path, PackageSpec], object],
) -> bool:
    """Run the requested scenarios; True if any of them fell short."""
    failed = False
    with session(
        args.directory,
        report_dir=args.report_dir,
        data_file=args.data_file,
        weaver=WeaverSpec(
            registry=_absolute(args.registry),
            policies=_absolute(args.policies),
            advice_data=_absolute(args.advice_data),
            config=_absolute(args.weaver_config),
        ),
        server=ServerSpec(
            run=tuple(shlex.split(args.server)) if args.server else None,
            health=args.server_health,
            url_var=args.server_url_var,
        ),
        env=dict(args.env),
        variables=dict(args.var),
        spec=spec,
        # Passed only when asked: a wrapping session factory may have its own
        # reduction, which an explicit default would override.
        **({"build_data": run_data_command} if args.data_command else {}),
    ) as opened:
        spec = opened.spec
        print(
            _paint(
                f"==== instrumented: {spec.instrumented_library}, "
                f"instrumentation: {spec.instrumentation_library}, "
                # The declared libraries name what was measured; the directory
                # is which package measured it, and two of them can declare
                # the same instrumentation.
                f"package: {Path(spec.directory).name}",
                "bold",
            )
        )
        for name in args.scenarios or opened.spec.scenarios:
            report = opened.run(name)
            # --report-only downgrades violations to warnings; a scenario that
            # crashed or missed what it declared still fails.
            violation_mark = _WARN if args.report_only else _FAIL
            if report.failures or (
                report.violations and violation_mark is _FAIL
            ):
                failed = True
                _status(_FAIL, f"scenario: {report.name}, status: FAIL")
            elif report.violations:
                _status(_WARN, f"scenario: {report.name}, status: WARN")
            else:
                _status(_OK, f"scenario: {report.name}, status: ok")
            _findings(_FAIL, "Failures", report.failures)
            _findings(violation_mark, "Violations", report.violations)
            if report.violations and violation_mark is _FAIL:
                print(
                    _paint(
                        "  declare them under expected_violations with a "
                        "reason, or fix them",
                        "dim",
                    )
                )
    return failed


def cli() -> None:
    """Console-script entry point."""
    # A finding carries whatever text weaver produced, which a legacy console
    # codepage would raise on rather than print.
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
    sys.exit(main())


if __name__ == "__main__":
    cli()
