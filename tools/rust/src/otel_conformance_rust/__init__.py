# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Build and directly run the Rust scenario in the current directory."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Sequence, cast

MANIFEST = "Cargo.toml"
PROFILE = "release"
RUN = "run"

CARGO_MISSING = "cargo was not found"
BINARY_MISSING = (
    "scenario binary was not found; run "
    "`otel-conformance-rust build` first"
)


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
    """Find the Cargo workspace root for the package at ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        manifest = candidate / MANIFEST
        if manifest.is_file() and _has_section(manifest, "workspace"):
            return candidate
        declared = (
            _section_value(manifest, "package", "workspace")
            if manifest.is_file()
            else None
        )
        if declared is not None:
            workspace = (candidate / declared).resolve()
            workspace_manifest = workspace / MANIFEST
            if workspace_manifest.is_file() and _has_section(
                workspace_manifest, "workspace"
            ):
                return workspace
            raise LayoutError(
                f"{manifest} declares workspace {declared!r}, but "
                f"{workspace_manifest} has no [workspace]"
            )
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


def target_directory(manifest: Path) -> Path:
    """Return the target directory Cargo resolves for ``manifest``."""
    result = subprocess.run(
        [
            "cargo",
            "metadata",
            "--format-version",
            "1",
            "--no-deps",
            "--locked",
            "--manifest-path",
            str(manifest),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(
        stream.strip()
        for stream in (result.stderr, result.stdout)
        if stream and stream.strip()
    )
    if result.returncode:
        detail = output or f"exit code {result.returncode}"
        raise LayoutError(f"cargo metadata failed for {manifest}: {detail}")
    try:
        metadata = cast(dict[str, object], json.loads(result.stdout))
    except json.JSONDecodeError as error:
        detail = output or "no output"
        raise LayoutError(
            f"cargo metadata returned invalid JSON for {manifest}: {detail}"
        ) from error
    target = metadata.get("target_directory")
    if not isinstance(target, str):
        raise LayoutError(
            f"cargo metadata for {manifest} has no target_directory"
        )
    return Path(target)


def binary(target: Path, manifest: Path) -> Path:
    """Return the absolute release binary path for ``manifest``."""
    suffix = ".exe" if os.name == "nt" else ""
    return (target / PROFILE / f"{package_name(manifest)}{suffix}").resolve()


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
    target: Path, manifest: Path, arguments: Sequence[str] = ()
) -> list[str]:
    """Execute the binary produced by :func:`build_command`."""
    return [str(binary(target, manifest)), *arguments]


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
        RUN,
        help="run the compiled scenario; unrecognized arguments are passed to it",
    )

    words = list(sys.argv[1:] if argv is None else argv)
    arguments, scenario_arguments = parser.parse_known_args(words)
    if arguments.command != RUN and scenario_arguments:
        parser.error(
            f"unrecognized arguments: {' '.join(scenario_arguments)}"
        )
    try:
        manifest = package_manifest()
        workspace_root(manifest.parent)
        # Each call names the program it could not start, because a
        # `FileNotFoundError` says which one only on some platforms: Windows
        # raises it out of `CreateProcess`, which leaves `filename` unset.
        if arguments.command == RUN:
            try:
                target = target_directory(manifest)
            except FileNotFoundError:
                return _fail(parser, CARGO_MISSING)
            command = run_command(target, manifest, scenario_arguments)
            absent = BINARY_MISSING
        else:
            command = build_command(manifest)
            absent = CARGO_MISSING
        try:
            return subprocess.call(command)  # noqa: S603
        except FileNotFoundError:
            return _fail(parser, absent)
    except LayoutError as error:
        return _fail(parser, str(error))


def _fail(parser: argparse.ArgumentParser, message: str) -> int:
    print(f"{parser.prog}: error: {message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
