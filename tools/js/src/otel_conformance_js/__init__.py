# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-js``: installs a Node conformance build.

A scenario is started with plain ``node``, which is an executable on every
platform. ``npm`` is not — it is a shell script with a ``.cmd`` shim on
Windows, and the runner starts a declared command directly rather than through
a shell — so the one Node step a ``conformance.yaml`` cannot name portably is
the install. That step is here instead.

``install``
    What a package's ``setup:`` runs. Installs the whole npm workspace from
    its committed lockfile, so a scenario gets the versions the lockfile pins
    rather than whatever resolves today.

``relock``
    Regenerates every committed ``package-lock.json`` under ``scenarios/``
    and ``tools/`` in place, changing only what the manifests require. What
    CI runs on a Renovate PR, and what a maintainer runs by hand when a
    lockfile is stale.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

# The file that marks the root of the Node build. Searched for upwards from the
# scenario directory, so a scenario says nothing about how deep it is nested.
BUILD_MARKER = "package-lock.json"


class LayoutError(RuntimeError):
    """The Node build could not be found from where this was run."""


def build_root(start: Path | None = None) -> Path:
    """The directory holding :data:`BUILD_MARKER`, at or above ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / BUILD_MARKER).is_file():
            return candidate
    raise LayoutError(
        f"no {BUILD_MARKER} at or above {here} — `otel-conformance-js` runs "
        "from a scenario directory inside a Node conformance build"
    )


def npm_command() -> list[str]:
    """``npm ci``, with npm found the way the shell would have found it.

    ``shutil.which`` rather than the bare name: on Windows npm is
    ``npm.cmd``, which the runner's direct ``CreateProcess`` would not find.
    """
    return [shutil.which("npm") or "npm", "ci"]


RELOCK = "relock"


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
    """Every directory under scenarios/ or tools/ with a tracked lockfile."""
    result = subprocess.run(
        [  # noqa: S607
            "git",
            "ls-files",
            "-z",
            "--",
            f":(glob)scenarios/**/{BUILD_MARKER}",
            f":(glob)tools/**/{BUILD_MARKER}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    listed = (path for path in result.stdout.split("\0") if path)
    return sorted({(root / path).parent for path in listed})


def relock_command() -> list[str]:
    """Rewrite the lockfile only: nothing installed, no scripts run."""
    return [
        shutil.which("npm") or "npm",
        "install",
        "--package-lock-only",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
    ]


def relock(root: Path | None = None) -> int:
    """Relock every project, stopping at the first that fails."""
    root = root or repository_root()
    for project in lock_projects(root):
        name = project.relative_to(root).as_posix()
        print(f"relocking {name}", flush=True)
        status = subprocess.call(relock_command(), cwd=project)  # noqa: S603
        if status != 0:
            print(f"relocking {name} failed", file=sys.stderr)
            return status
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-js",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "install", help="install the workspace from its committed lockfile"
    )
    subcommands.add_parser(
        RELOCK,
        help="regenerate every committed package-lock.json in place",
    )

    arguments = parser.parse_args(argv)
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
    try:
        root = build_root()
    except LayoutError as error:
        print(error, file=sys.stderr)
        return 1
    # From the build root, so every scenario in it installs the same tree
    # however deep its own directory sits.
    try:
        return subprocess.call(npm_command(), cwd=root)  # noqa: S603
    except FileNotFoundError:
        # A `setup:` step reports what it printed, so what is missing should be
        # the first line of it rather than the bottom of a traceback.
        print(
            "npm is not on PATH, and a Node scenario is built with it",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
