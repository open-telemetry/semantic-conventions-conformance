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

    parser.parse_args(argv)
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
