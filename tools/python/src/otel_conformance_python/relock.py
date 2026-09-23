# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-python-relock`` — relock every committed uv project.

Runs ``uv lock`` in every directory under ``scenarios/`` and ``tools/`` with a
committed ``uv.lock``, changing only what the manifests require. What CI runs
on a Renovate PR, and what a maintainer runs by hand when a lock is stale.

A script of its own rather than a subcommand: ``otel-conformance-python``
takes the scenario program as its only argument.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

LOCKFILE = "uv.lock"


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
    """Every directory under scenarios/ or tools/ with a tracked uv.lock."""
    result = subprocess.run(
        [  # noqa: S607
            "git",
            "ls-files",
            "-z",
            "--",
            f":(glob)scenarios/**/{LOCKFILE}",
            f":(glob)tools/**/{LOCKFILE}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    listed = (path for path in result.stdout.split("\0") if path)
    return sorted({(root / path).parent for path in listed})


def relock_command() -> list[str]:
    return [shutil.which("uv") or "uv", "lock"]


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
        prog="otel-conformance-python-relock",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.parse_args(argv)
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


def cli() -> None:
    """Console-script entry point."""
    sys.exit(main())


if __name__ == "__main__":
    cli()
