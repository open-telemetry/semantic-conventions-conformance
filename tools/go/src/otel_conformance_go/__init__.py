# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-go``: builds and runs a Go conformance scenario.

Every Go scenario is built and started the same way — compile the package in
the scenario directory, then execute what came out — so the toolchain lives
here rather than being restated in each ``conformance.yaml``.

Three subcommands, matching the two phases a package has, plus lock
maintenance:

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

``relock``
    Runs ``go mod tidy`` in every committed Go module under ``scenarios/``
    and ``tools/``: the ``tools/`` modules first, because the scenario
    module pulls them in through ``replace`` and tidies against their
    requirements. What CI runs on a Renovate PR, and what a maintainer runs
    by hand when a ``go.sum`` is stale.
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
# scenario rather than under the module root: a Go scenario's package *is* its
# directory, so there is nothing to flatten.
BUILD_DIR = "build"

BINARY = "scenario"

RUN = "run"

RELOCK = "relock"


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
    return ["go", "build", "-o", str(binary(directory)), "."]


def run_command(
    directory: Path, arguments: Sequence[str] = ()
) -> list[str]:
    return [str(binary(directory)), *arguments]


def repository_root(start: Path | None = None) -> Path:
    """The top of the git repository ``start`` is in."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
        cwd=start or Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(result.stdout.strip())


def lock_projects(root: Path) -> list[Path]:
    """Every tracked Go module under scenarios/ or tools/, tools/ first."""
    result = subprocess.run(
        [  # noqa: S607
            "git",
            "ls-files",
            "-z",
            "--",
            f":(glob)scenarios/**/{MODULE_MARKER}",
            f":(glob)tools/**/{MODULE_MARKER}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    listed = (path for path in result.stdout.split("\0") if path)
    modules = {(root / path).parent for path in listed}
    return sorted(
        modules,
        key=lambda module: (
            module.relative_to(root).parts[0] != "tools",
            module,
        ),
    )


def relock_command() -> list[str]:
    return ["go", "mod", "tidy"]


def relock(root: Path | None = None) -> int:
    """Tidy every module, stopping at the first that fails."""
    root = root or repository_root()
    for module in lock_projects(root):
        name = module.relative_to(root).as_posix()
        print(f"relocking {name}", flush=True)
        status = subprocess.call(relock_command(), cwd=module)  # noqa: S603
        if status != 0:
            print(f"relocking {name} failed", file=sys.stderr)
            return status
    return 0


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

    subcommands.add_parser(
        RELOCK,
        help="tidy every committed Go module in the repository",
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
    if arguments.command == RELOCK:
        try:
            return relock()
        except subprocess.CalledProcessError:
            print(
                "`relock` runs inside the conformance git repository",
                file=sys.stderr,
            )
            return 1
        except FileNotFoundError as error:
            print(f"could not start {error.filename}", file=sys.stderr)
            return 1
    directory = Path.cwd()
    module_root(directory)

    if arguments.command == RUN:
        command = run_command(directory, scenario_arguments)
    else:
        binary(directory).parent.mkdir(parents=True, exist_ok=True)
        command = build_command(directory)

    return subprocess.call(command)  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
