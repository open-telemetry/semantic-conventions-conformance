# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Install and run a Ruby conformance package with its committed bundle."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

GEMFILE = "Gemfile"
LOCKFILE = "Gemfile.lock"
BUNDLE_DIRECTORY = Path("vendor") / "bundle"
RUN = "run"


class LayoutError(RuntimeError):
    """The Ruby package or requested entry point could not be found."""


class ToolError(RuntimeError):
    """A program required by the Ruby launcher could not be found."""


def package_root(start: Path | None = None) -> Path:
    """Find the nearest directory containing both a Gemfile and its lock."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        gemfile = (candidate / GEMFILE).is_file()
        lockfile = (candidate / LOCKFILE).is_file()
        if gemfile and lockfile:
            return candidate
        if gemfile or lockfile:
            missing = LOCKFILE if gemfile else GEMFILE
            found = GEMFILE if gemfile else LOCKFILE
            raise LayoutError(
                f"found {found} at {candidate}, but {missing} is missing — "
                "Ruby conformance packages must commit their resolved bundle"
            )
    raise LayoutError(
        f"no {GEMFILE} and {LOCKFILE} at or above {here} — "
        "`otel-conformance-ruby` runs from inside a Ruby conformance package"
    )


def executable(name: str) -> str:
    """Find an executable the same way a shell would, or report its absence."""
    found = shutil.which(name)
    if found is None:
        raise ToolError(
            f"{name} is not on PATH, and a Ruby scenario requires it"
        )
    return found


def bundle_command(*arguments: str) -> list[str]:
    """Create a Bundler command that works with Unix scripts and Windows shims."""
    ruby = executable("ruby")
    executable("bundle")
    # Ruby's -S performs PATH lookup itself and can run Bundler's Ruby script on
    # Windows without asking CreateProcess to execute a .bat or .cmd shim.
    return [ruby, "-S", "bundle", *arguments]


def run_command(entry: Path, arguments: Sequence[str] = ()) -> list[str]:
    """Create the bundled Ruby invocation for one scenario entry point."""
    ruby = executable("ruby")
    executable("bundle")
    return [
        ruby,
        "-S",
        "bundle",
        "exec",
        ruby,
        str(entry),
        *arguments,
    ]


def bundle_environment(
    root: Path, environ: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Return an environment selecting the package's locked, local bundle."""
    environment = dict(os.environ if environ is None else environ)
    bundle_directory = str(root / BUNDLE_DIRECTORY)
    for variable in (
        "BUNDLE_DISABLE_SHARED_GEMS",
        "BUNDLE_PATH",
        "GEM_HOME",
        "GEM_PATH",
    ):
        environment.pop(variable, None)
    environment.update(
        {
            "BUNDLE_DISABLE_SHARED_GEMS": "true",
            "BUNDLE_FROZEN": "true",
            "BUNDLE_GEMFILE": str(root / GEMFILE),
            "BUNDLE_IGNORE_CONFIG": "true",
            "BUNDLE_PATH": bundle_directory,
        }
    )
    return environment


def _entry_path(word: str) -> Path:
    entry = Path(word)
    if not entry.is_absolute():
        entry = Path.cwd() / entry
    entry = entry.resolve()
    if not entry.is_file():
        raise LayoutError(f"Ruby scenario entry point does not exist: {entry}")
    return entry


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-ruby",
        description=__doc__,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "install", help="install the package from its committed lockfile"
    )
    run = subcommands.add_parser(
        RUN, help="execute a Ruby entry point in the package's bundle"
    )
    run.add_argument("entry", help="Ruby file to execute")
    run.add_argument(
        "arguments",
        nargs=argparse.REMAINDER,
        help="arguments passed to the Ruby program, verbatim",
    )

    arguments = parser.parse_args(argv)
    try:
        root = package_root()
        environment = bundle_environment(root)
        if arguments.command == "install":
            command = bundle_command("install")
        else:
            command = run_command(
                _entry_path(arguments.entry), arguments.arguments
            )
        return subprocess.call(  # noqa: S603
            command,
            cwd=root,
            env=environment,
        )
    except (LayoutError, ToolError) as error:
        print(error, file=sys.stderr)
        return 1
    except FileNotFoundError as error:
        print(f"could not start Ruby tooling: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
