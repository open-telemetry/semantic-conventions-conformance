# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Install and serve a PHP conformance scenario."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import BinaryIO, Sequence

BUILD_MARKER = "composer.json"
PORT_VARIABLE = "OTEL_HTTP_SCENARIO_PORT"
_READ_BUFFER_SIZE = 8192
_POLL_INTERVAL_SECONDS = 0.05
_SHUTDOWN_TIMEOUT_SECONDS = 10


class LayoutError(RuntimeError):
    """The PHP package or requested router could not be found."""


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


def serve(
    router: Path,
    *,
    input_stream: BinaryIO | None = None,
) -> int:
    """Serve until the driver's standard input closes."""
    port = _required_env(PORT_VARIABLE)
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
        stream = input_stream or sys.stdin.buffer
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

    process.terminate()
    try:
        process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
        return 0
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="otel-conformance-php")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "install",
        help="install the nearest Composer package from its lockfile",
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
        try:
            return subprocess.call(composer_command(), cwd=root)  # noqa: S603
        except FileNotFoundError as error:
            raise LayoutError(
                "composer is not on PATH, and a PHP scenario is installed with it"
            ) from error
    except LayoutError as error:
        print(error, file=sys.stderr)
        return 1


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise LayoutError(f"required environment variable is missing: {name}")

    return value


if __name__ == "__main__":
    sys.exit(main())
