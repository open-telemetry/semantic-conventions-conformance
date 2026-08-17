# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-go``: builds and runs a Go conformance scenario.

Every Go scenario is built and started the same way — compile the package in
the scenario directory, then execute what came out — so the toolchain lives
here rather than being restated in each ``conformance.yaml``.

Two subcommands, matching the two phases a package has:

``build``
    What a package's ``setup:`` runs. Compiles the scenario ahead of the
    measured run, so no toolchain is on the clock and no compilation shows up
    as the scenario's own work.

``run``
    What a scenario's ``run:`` runs. Executes the built binary by absolute
    path, which is the reason this exists at all: Windows resolves a relative
    command against the *calling* process's directory rather than the working
    directory it is given, and only there does the binary need an ``.exe``
    suffix. Naming the binary in a scenario file would make the file
    platform-specific. Everything after ``run`` is the scenario's own, passed
    on verbatim.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

# The file that marks the root of the Go module a scenario belongs to. Only
# reported on: `go build` finds it itself, but a scenario outside a module
# fails deep inside the toolchain rather than here.
MODULE_MARKER = "go.mod"

# Where the binary goes, relative to the scenario directory. Beside the
# scenario rather than under the module root: unlike a Gradle project, a Go
# scenario's package *is* its directory, so there is nothing to flatten.
BUILD_DIR = "build"

BINARY = "scenario"

# The subcommand whose remaining words belong to the scenario rather than to
# this program.
RUN = "run"


class LayoutError(RuntimeError):
    """The Go module could not be found from where this was run."""


def module_root(start: Path | None = None) -> Path:
    """The directory holding :data:`MODULE_MARKER`, at or above ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / MODULE_MARKER).is_file():
            return candidate
    raise LayoutError(
        f"no {MODULE_MARKER} at or above {here} — `otel-conformance-go` runs "
        "from a scenario directory inside a Go conformance module"
    )


def binary(directory: Path) -> Path:
    """Where ``directory``'s scenario binary is built.

    Absolute, and carrying the platform's executable suffix, so the same
    ``conformance.yaml`` runs on every platform.
    """
    return (
        directory.resolve()
        / BUILD_DIR
        / (BINARY + (".exe" if os.name == "nt" else ""))
    )


def build_command(directory: Path) -> list[str]:
    """The ``go build`` invocation for the scenario in ``directory``."""
    return ["go", "build", "-o", str(binary(directory)), "."]


def run_command(
    directory: Path, arguments: Sequence[str] = ()
) -> list[str]:
    """The invocation of what :func:`build_command` produced."""
    return [str(binary(directory)), *arguments]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-go",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser(
        "build", help="compile the scenario in the current directory"
    )

    subcommands.add_parser(
        RUN,
        help="run the built scenario; what follows is the scenario's own",
    )

    # Split off rather than declared as a trailing positional: argparse reads
    # a leading `-` as an option of this program whatever a positional's
    # `nargs` says, so `run --flag` would be refused before the scenario ever
    # saw it. `build` keeps being parsed strictly, so a typo there still says
    # so.
    words = list(sys.argv[1:] if argv is None else argv)
    scenario_arguments: list[str] = []
    if words and words[0] == RUN:
        words, scenario_arguments = words[:1], words[1:]

    arguments = parser.parse_args(words)
    directory = Path.cwd()
    module_root(directory)

    if arguments.command == RUN:
        command = run_command(directory, scenario_arguments)
    else:
        command = build_command(directory)

    return subprocess.call(command)  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
