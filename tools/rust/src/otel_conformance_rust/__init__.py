# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Build and directly run the Rust scenario in the current directory."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence

MANIFEST = "Cargo.toml"
TARGET = "target"
PROFILE = "release"
RUN = "run"


class LayoutError(RuntimeError):
    """The Rust package or workspace could not be found."""


def package_manifest(start: Path | None = None) -> Path:
    """Find the nearest Cargo package manifest at or above ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        manifest = candidate / MANIFEST
        if manifest.is_file() and _section_value(manifest, "package", "name"):
            return manifest
    raise LayoutError(
        f"no package {MANIFEST} at or above {here} — "
        "`otel-conformance-rust` runs from inside a Cargo package"
    )


def workspace_root(start: Path | None = None) -> Path:
    """Find the Cargo workspace root at or above ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        manifest = candidate / MANIFEST
        if manifest.is_file() and _has_section(manifest, "workspace"):
            return candidate
    raise LayoutError(
        f"no workspace {MANIFEST} at or above {here} — "
        "`otel-conformance-rust` runs from inside a Cargo workspace"
    )


def package_name(manifest: Path) -> str:
    """Return the package name declared by ``manifest``."""
    name = _section_value(manifest, "package", "name")
    if name is None:
        raise LayoutError(f"{manifest} has no [package] name")
    return name


def binary(root: Path, manifest: Path) -> Path:
    """Return the absolute release binary path for ``manifest``."""
    suffix = ".exe" if os.name == "nt" else ""
    return (root / TARGET / PROFILE / f"{package_name(manifest)}{suffix}").resolve()


def build_command(manifest: Path) -> list[str]:
    """Build only the scenario package, in release mode."""
    return [
        "cargo",
        "build",
        "--release",
        "--locked",
        "--manifest-path",
        str(manifest),
    ]


def run_command(
    root: Path, manifest: Path, arguments: Sequence[str] = ()
) -> list[str]:
    """Execute the binary produced by :func:`build_command`."""
    return [str(binary(root, manifest)), *arguments]


def _has_section(manifest: Path, section: str) -> bool:
    pattern = re.compile(rf"^\s*\[{re.escape(section)}\]\s*(?:#.*)?$")
    return any(
        pattern.match(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
    )


def _section_value(
    manifest: Path, section: str, key: str
) -> str | None:
    section_pattern = re.compile(
        rf"^\s*\[{re.escape(section)}\]\s*(?:#.*)?$"
    )
    key_pattern = re.compile(
        rf"""^\s*{re.escape(key)}\s*=\s*(?:"([^"]+)"|'([^']+)')\s*(?:#.*)?$"""
    )
    in_section = False
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("["):
            in_section = bool(section_pattern.match(line))
            continue
        if in_section and (match := key_pattern.match(line)):
            return match.group(1) or match.group(2)
    return None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-rust",
        description=__doc__,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("build", help="compile this scenario in release mode")
    subcommands.add_parser(
        RUN, help="run the compiled scenario; remaining words are passed through"
    )

    words = list(sys.argv[1:] if argv is None else argv)
    scenario_arguments: list[str] = []
    if words and words[0] == RUN:
        words, scenario_arguments = words[:1], words[1:]

    arguments = parser.parse_args(words)
    manifest = package_manifest()
    root = workspace_root(manifest.parent)
    command = (
        run_command(root, manifest, scenario_arguments)
        if arguments.command == RUN
        else build_command(manifest)
    )
    return subprocess.call(command)  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
