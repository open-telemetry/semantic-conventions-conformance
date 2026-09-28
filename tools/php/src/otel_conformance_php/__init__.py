# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Install and serve a PHP conformance scenario."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, BinaryIO, Sequence

BUILD_MARKER = "composer.json"
# What a lock copies from a path package's ``composer.json`` and what runs.
_SNAPSHOT_KEYS = (
    "require",
    "require-dev",
    "conflict",
    "replace",
    "provide",
    "autoload",
    "bin",
)
PORT_VARIABLE = "OTEL_HTTP_SCENARIO_PORT"
_READ_BUFFER_SIZE = 8192
_POLL_INTERVAL_SECONDS = 0.05
_SHUTDOWN_TIMEOUT_SECONDS = 10


class LayoutError(RuntimeError):
    """A PHP scenario prerequisite is missing or invalid."""


def package_root(start: Path | None = None) -> Path:
    """Find the nearest Composer package at or above ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / BUILD_MARKER).is_file():
            return candidate
    raise LayoutError(
        f"no {BUILD_MARKER} at or above {here} - "
        "`otel-conformance-php` runs inside a Composer package"
    )


def composer_command() -> list[str]:
    """The portable Composer install command."""
    return [
        shutil.which("composer") or "composer",
        "install",
        "--no-interaction",
        "--no-progress",
        "--prefer-dist",
    ]


def php_command(port: str, router: Path) -> list[str]:
    """The PHP built-in server command for ``router``."""
    return [
        shutil.which("php") or "php",
        "-S",
        f"127.0.0.1:{port}",
        str(router),
    ]


def path_packages(lock: Path) -> list[str]:
    """Names of the locked packages that were installed from a local path."""
    data = json.loads(lock.read_text(encoding="utf-8"))
    return sorted(
        package["name"]
        for section in ("packages", "packages-dev")
        for package in data.get(section, [])
        if package.get("dist", {}).get("type") == "path"
    )


def check_lock(root: Path) -> None:
    """Fail if the lock at ``root`` disagrees with its path packages.

    A lock snapshots each path package's requirements, and ``composer install``
    neither notices nor fails when a snapshot is stale, so the scenario would
    keep running dependencies its path packages no longer ask for.
    """
    problems = lock_problems(root)
    if not problems:
        return

    lock = root / "composer.lock"
    packages = " ".join(path_packages(lock))
    listed = "".join(f"\n  - {problem}" for problem in problems)
    raise LayoutError(
        f"{lock} is out of date with its path packages:{listed}\n"
        f"Run `composer update {packages} --with-dependencies` in {root} "
        "and commit the lock"
    )


def lock_problems(root: Path) -> list[str]:
    """How the lock at ``root`` disagrees with its path packages, if it does.

    Offline: it reads the lock, each path package's ``composer.json`` and, when
    it has one, its ``composer.lock``.
    """
    lock = root / "composer.lock"
    if not lock.is_file():
        return []

    locked = _locked_packages(_read_json(lock))
    problems: list[str] = []
    for name, entry in sorted(locked.items()):
        dist = entry.get("dist", {})
        if dist.get("type") != "path":
            continue
        url = dist.get("url", "")
        source = (root / url).resolve()
        manifest = source / "composer.json"
        if not manifest.is_file():
            problems.append(f"{name}: there is no composer.json at {url}")
            continue

        declared = _read_json(manifest)
        problems.extend(_snapshot_problems(name, entry, declared, url))
        problems.extend(
            _version_problems(name, locked, declared, source / "composer.lock")
        )
    return problems


def _snapshot_problems(
    name: str,
    entry: dict[str, Any],
    declared: dict[str, Any],
    url: str,
) -> list[str]:
    """Where the lock's copy of a package differs from its source."""
    problems: list[str] = []
    for key in _SNAPSHOT_KEYS:
        if (entry.get(key) or None) != (declared.get(key) or None):
            problems.append(
                f"{name}: the lock has {key} {_show(entry.get(key))} but "
                f"{url}/composer.json has {_show(declared.get(key))}"
            )
    if entry.get("type", "library") != declared.get("type", "library"):
        problems.append(
            f"{name}: the lock has type {_show(entry.get('type'))} but "
            f"{url}/composer.json has {_show(declared.get('type'))}"
        )
    return problems


def _version_problems(
    name: str,
    locked: dict[str, dict[str, Any]],
    declared: dict[str, Any],
    package_lock: Path,
) -> list[str]:
    """Where a direct dependency's locked version is not the one the path
    package's own lock, which is what its tests run against, pins."""
    if not package_lock.is_file():
        return []

    tested = {
        dependency: package["version"]
        for dependency, package in _locked_packages(
            _read_json(package_lock)
        ).items()
    }
    problems: list[str] = []
    for dependency in sorted(declared.get("require", {})):
        if "/" not in dependency or dependency not in tested:
            continue  # a platform requirement, or not locked by the package
        version = locked.get(dependency, {}).get("version")
        if version != tested[dependency]:
            problems.append(
                f"{name}: {dependency} is locked at {version or 'nothing'} "
                f"but the package's own composer.lock pins {tested[dependency]}"
            )
    return problems


def _locked_packages(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        package["name"]: package
        for section in ("packages", "packages-dev")
        for package in lock.get(section, [])
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise LayoutError(f"{path} is not valid JSON: {error}") from error


def _show(value: object) -> str:
    return "nothing" if value is None else json.dumps(value, sort_keys=True)


def serve(
    router: Path,
    *,
    input_stream: BinaryIO | None = None,
) -> int:
    """Serve until the driver's standard input closes."""
    port = _required_port(PORT_VARIABLE)
    resolved = router.resolve()
    if not resolved.is_file():
        raise LayoutError(f"PHP router does not exist: {resolved}")

    try:
        process = subprocess.Popen(  # noqa: S603
            php_command(port, resolved),
            stdin=subprocess.DEVNULL,
        )
    except FileNotFoundError as error:
        raise LayoutError(
            "serving a PHP scenario requires php to be available on PATH"
        ) from error

    closed = threading.Event()

    def wait_for_eof() -> None:
        stream = sys.stdin.buffer if input_stream is None else input_stream
        while stream.read(_READ_BUFFER_SIZE):
            pass
        closed.set()

    reader = threading.Thread(target=wait_for_eof, daemon=True)
    reader.start()

    while not closed.wait(_POLL_INTERVAL_SECONDS):
        status = process.poll()
        if status is not None:
            return status if status != 0 else 1

    if process.poll() is not None:
        return process.returncode or 0

    try:
        process.terminate()
    except OSError:
        pass
    try:
        process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
        return 0
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="otel-conformance-php")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "install",
        help="install the nearest Composer package from its lockfile, "
        "failing first if the lock is stale",
    )
    subcommands.add_parser(
        "check-lock",
        help="fail if the nearest Composer lock disagrees with its path "
        "packages",
    )
    serve_parser = subcommands.add_parser(
        "serve",
        help="serve a PHP router until standard input closes",
    )
    serve_parser.add_argument("router", type=Path)

    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "serve":
            return serve(arguments.router)

        root = package_root()
        check_lock(root)
        if arguments.command == "check-lock":
            return 0

        try:
            return subprocess.call(composer_command(), cwd=root)  # noqa: S603
        except FileNotFoundError as error:
            raise LayoutError(
                "installing PHP scenario dependencies requires composer on PATH"
            ) from error
    except LayoutError as error:
        print(error, file=sys.stderr)
        return 1


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise LayoutError(f"required environment variable is missing: {name}")

    return value


def _required_port(name: str) -> str:
    value = _required_env(name)
    if not value.isascii() or not value.isdecimal():
        raise LayoutError(
            f"{name} must be an integer from 1 to 65535: {value}"
        )

    port = int(value)
    if not 1 <= port <= 65535:
        raise LayoutError(
            f"{name} must be an integer from 1 to 65535: {value}"
        )

    return value


if __name__ == "__main__":
    sys.exit(main())
