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
    rather than whatever resolves today. With ``--browser chromium``, it also
    installs the pinned Playwright browser used by browser scenarios.
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


def playwright_command(root: Path, browser: str) -> list[str]:
    """The workspace's pinned Playwright CLI, without relying on a shell shim."""
    executable = root / "node_modules" / "playwright" / "cli.js"
    command = [shutil.which("node") or "node", str(executable), "install"]
    if sys.platform == "linux":
        command.append("--with-deps")
    return [*command, browser]


def run_command(command: Sequence[str], root: Path) -> int:
    """Runs ``command`` from ``root``, naming it when it is not there to run.

    A ``setup:`` step reports what it printed, so a missing executable should
    be the first line of that rather than the bottom of a traceback. The name
    comes from the command itself: on Windows the raised
    ``FileNotFoundError`` carries no ``filename``, so the exception alone
    cannot say what was missing.
    """
    try:
        return subprocess.call(command, cwd=root)  # noqa: S603
    except FileNotFoundError:
        print(
            f"{command[0]} is not available, and a Node scenario requires it",
            file=sys.stderr,
        )
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-js",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    install = subcommands.add_parser(
        "install", help="install the workspace from its committed lockfile"
    )
    install.add_argument(
        "--browser",
        choices=("chromium",),
        help="also install the workspace's pinned Playwright browser",
    )

    arguments = parser.parse_args(argv)
    try:
        root = build_root()
    except LayoutError as error:
        print(error, file=sys.stderr)
        return 1
    # From the build root, so every scenario in it installs the same tree
    # however deep its own directory sits.
    result = run_command(npm_command(), root)
    if result != 0 or arguments.browser is None:
        return result
    return run_command(playwright_command(root, arguments.browser), root)


if __name__ == "__main__":
    sys.exit(main())
