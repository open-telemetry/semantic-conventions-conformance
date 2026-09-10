# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Build and directly run the Rust scenario in the current directory."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CargoPackage:
    """The Cargo paths and binary target for a scenario package."""

    manifest: Path
    target_directory: Path
    binary_name: str


def package_manifest(start: Path | None = None) -> Path:
    """Find the nearest Cargo package manifest at or above ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        manifest = candidate / MANIFEST
        if manifest.is_file():
            return manifest
    raise LayoutError(
        f"no package {MANIFEST} at or above {here} — "
        "`otel-conformance-rust` runs from inside a Cargo package"
    )


def cargo_package(manifest: Path) -> CargoPackage:
    """Return Cargo's resolved layout for the scenario package."""
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

    target_directory = metadata.get("target_directory")
    package_values = metadata.get("packages")
    if not isinstance(target_directory, str) or not isinstance(
        package_values, list
    ):
        raise LayoutError(
            f"cargo metadata for {manifest} has an invalid package layout"
        )

    package: dict[str, object] | None = None
    resolved_manifest = manifest.resolve()
    for value in cast(list[object], package_values):
        if not isinstance(value, dict):
            continue
        candidate = cast(dict[str, object], value)
        candidate_manifest = candidate.get("manifest_path")
        if (
            isinstance(candidate_manifest, str)
            and Path(candidate_manifest).resolve() == resolved_manifest
        ):
            package = candidate
            break
    if package is None:
        raise LayoutError(f"{manifest} is not a Cargo package manifest")

    target_values = package.get("targets")
    if not isinstance(target_values, list):
        raise LayoutError(f"cargo metadata for {manifest} has no targets")
    binaries: list[str] = []
    for value in cast(list[object], target_values):
        if not isinstance(value, dict):
            continue
        cargo_target = cast(dict[str, object], value)
        name = cargo_target.get("name")
        kinds = cargo_target.get("kind")
        if (
            isinstance(name, str)
            and isinstance(kinds, list)
            and "bin" in kinds
        ):
            binaries.append(name)

    default_run = package.get("default_run")
    if isinstance(default_run, str):
        if default_run not in binaries:
            raise LayoutError(
                f"cargo metadata for {manifest} has an invalid default-run "
                f"target {default_run!r}"
            )
        binary_name = default_run
    elif len(binaries) == 1:
        binary_name = binaries[0]
    elif not binaries:
        raise LayoutError(f"{manifest} has no binary target")
    else:
        raise LayoutError(
            f"{manifest} has multiple binary targets and no default-run"
        )

    return CargoPackage(
        manifest=resolved_manifest,
        target_directory=Path(target_directory),
        binary_name=binary_name,
    )


def binary(package: CargoPackage) -> Path:
    """Return the absolute release binary path for ``package``."""
    suffix = ".exe" if os.name == "nt" else ""
    return (
        package.target_directory
        / PROFILE
        / f"{package.binary_name}{suffix}"
    ).resolve()


def build_command(package: CargoPackage) -> list[str]:
    """Build only the scenario package, in release mode."""
    return [
        "cargo",
        "build",
        "--release",
        "--locked",
        "--manifest-path",
        str(package.manifest),
        "--bin",
        package.binary_name,
    ]


def run_command(
    package: CargoPackage, arguments: Sequence[str] = ()
) -> list[str]:
    """Execute the binary produced by :func:`build_command`."""
    return [str(binary(package)), *arguments]


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
        # Each call names the program it could not start, because a
        # `FileNotFoundError` says which one only on some platforms: Windows
        # raises it out of `CreateProcess`, which leaves `filename` unset.
        try:
            package = cargo_package(manifest)
        except FileNotFoundError:
            return _fail(parser, CARGO_MISSING)
        if arguments.command == RUN:
            command = run_command(package, scenario_arguments)
            absent = BINARY_MISSING
        else:
            command = build_command(package)
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
