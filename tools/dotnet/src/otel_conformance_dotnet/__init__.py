# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-dotnet``: builds and runs a .NET conformance scenario.

Every .NET scenario is prepared and started the same way — publish the project
the scenario directory belongs to, then run what came out — so the toolchain
lives here rather than being restated in each ``conformance.yaml``. Neither
subcommand takes an argument: a scenario directory sits inside its project, and
where a build root collects what it publishes is the build's business.

Two subcommands, matching the two phases a package has:

``build``
    What a package's ``setup:`` runs. Publishes the scenario's project ahead of
    the measured run, so no toolchain is on the clock and no compilation shows
    up as the scenario's own work.

``run``
    What a scenario's ``run:`` runs. Executes ``dotnet <assembly>`` rather than
    the published launcher executable, whose name is ``.exe`` on Windows and
    extensionless everywhere else, so naming it in a scenario file would make
    the file platform-specific. Everything after ``run`` is the scenario's own,
    passed on verbatim.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

# The file that marks the root of a .NET build. It is also where a build root
# declares `PublishDir`, and MSBuild resolves it the same way this does — the
# nearest one at or above the project — so both agree on where a published
# scenario lands.
BUILD_MARKER = "Directory.Build.props"

PROJECT_SUFFIX = ".csproj"

# Where `PublishDir` collects what `build` published, relative to the build
# root and flattened to one directory per project.
RUNTIME = Path("build") / "scenario-runtime"

CONFIGURATION = "Release"

# The subcommand whose remaining words belong to the scenario rather than to
# this program.
RUN = "run"


class LayoutError(RuntimeError):
    """The .NET project or build could not be found from where this was run."""


def project_file(start: Path | None = None) -> Path:
    """The project a scenario belongs to: the nearest ``.csproj`` above.

    A scenario directory sits inside the project that produces it, so how deep
    it is nested is the layout's business rather than the scenario's.
    """
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        projects = sorted(candidate.glob(f"*{PROJECT_SUFFIX}"))
        if len(projects) == 1:
            return projects[0]
        if projects:
            raise LayoutError(
                f"{candidate} holds {len(projects)} {PROJECT_SUFFIX} files — "
                "a scenario belongs to exactly one project"
            )
    raise LayoutError(
        f"no {PROJECT_SUFFIX} at or above {here} — `otel-conformance-dotnet` "
        "runs from a scenario directory inside a .NET conformance project"
    )


def build_root(start: Path | None = None) -> Path:
    """The directory holding :data:`BUILD_MARKER`, at or above ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / BUILD_MARKER).is_file():
            return candidate
    raise LayoutError(
        f"no {BUILD_MARKER} at or above {here} — `otel-conformance-dotnet` "
        "runs from a scenario directory inside a .NET conformance build"
    )


def publish_command(project: Path) -> list[str]:
    """The ``dotnet publish`` invocation for ``project``."""
    # No output path: a build root's `PublishDir` chooses it, so the build and
    # the scenario cannot disagree about where the assembly ends up.
    return [
        "dotnet",
        "publish",
        str(project),
        "--configuration",
        CONFIGURATION,
        "--nologo",
    ]


def run_command(
    root: Path, project: Path, arguments: Sequence[str] = ()
) -> list[str]:
    """The invocation of what :func:`publish_command` produced."""
    assembly = root / RUNTIME / project.stem / f"{project.stem}.dll"
    return ["dotnet", str(assembly), *arguments]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-dotnet",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser(
        "build", help="publish the project the current directory belongs to"
    )

    subcommands.add_parser(
        RUN,
        help="run the published scenario; what follows is the scenario's own",
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
    project = project_file()

    if arguments.command == RUN:
        # Resolved from the project's directory, which is where MSBuild
        # resolved the build root from when it published.
        command = run_command(
            build_root(project.parent), project, scenario_arguments
        )
    else:
        command = publish_command(project)

    return subprocess.call(command)  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
