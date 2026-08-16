# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-http-drive``: sends the request contract at a scenario's server.

A server scenario's telemetry is the only telemetry its run should hold, so
the requests are sent from outside it. This is the outside: it starts the
scenario, waits for it to answer, sends the contract with the standard
library, and closes the scenario's standard input so it flushes and exits.

The scenario itself is any command in any language. It learns which port to
bind from ``OTEL_HTTP_SCENARIO_PORT`` and inherits everything else — the OTLP
endpoint the runner injected included, which is why this runs as the scenario
command rather than as the runner's ``server:``.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from typing import Sequence

from . import (
    PORT_VARIABLE,
    drive,
    reserve_port,
    wait_for_health,
    wait_for_port,
)

# Generous: a cold JVM with a Java agent attached is slow to reach its first
# request, and a loaded CI machine slower still.
_STARTUP_TIMEOUT_SECONDS = 60
_SHUTDOWN_TIMEOUT_SECONDS = 30
_POLL_INTERVAL_SECONDS = 0.1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="otel-http-drive",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="base URL of a server that is already running",
    )
    parser.add_argument(
        "--serve",
        nargs=argparse.REMAINDER,
        metavar="COMMAND",
        help=(
            "the rest of the command line is a server scenario to start; it "
            f"binds ${{{PORT_VARIABLE}}} and exits when its standard input "
            "closes"
        ),
    )
    arguments = parser.parse_args(argv)

    if arguments.url is None:
        if arguments.serve is None:
            parser.error("give either a base URL or --serve COMMAND")
        if not arguments.serve:
            parser.error("--serve requires COMMAND")
        return _serve_and_drive(arguments.serve)
    if arguments.serve is not None:
        parser.error("give either a base URL or --serve COMMAND, not both")

    wait_for_health(arguments.url)
    drive(arguments.url)
    return 0


def _serve_and_drive(command: Sequence[str]) -> int:
    """Run ``command`` as a server, drive it, and report how it exited."""
    port, reservation = reserve_port()
    base_url = f"http://127.0.0.1:{port}"

    # Standard input is a pipe because closing it is the stop signal; output
    # is inherited so the scenario's own logging reaches the runner, which
    # shows it when something fails. Its own process group, because a scenario
    # command is often a launcher rather than the server itself: every Java
    # scenario runs as `otel-conformance-java run ...`, which makes the JVM a
    # grandchild, and killing the launcher alone would leave it running.
    reservation.close()
    process = subprocess.Popen(  # noqa: S603
        list(command),
        stdin=subprocess.PIPE,
        env={**os.environ, PORT_VARIABLE: str(port)},
        start_new_session=True,
    )

    try:
        _wait_for_start(process, port, base_url, command)
        drive(base_url)
    except BaseException:
        _kill_tree(process)
        raise

    return _stop(process)


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    """Kill the whole group the scenario was started in, then reap it.

    A scenario only reaches here when it did not stop on its own, so killing
    the command alone can leave the real server alive: still holding the port
    the next run wants, and still holding the output pipe the runner reads
    until this process's own timeout is hit rather than the scenario's.

    A group so a launcher passes it on; falling back to the direct child
    covers a group that has already gone, and Windows, where there is none.
    """
    if process.poll() is None:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (AttributeError, OSError):
            process.kill()
    process.wait()


def _wait_for_start(
    process: subprocess.Popen[bytes],
    port: int,
    base_url: str,
    command: Sequence[str],
) -> None:
    """Wait for the scenario to answer, or say why it never will.

    The port first, because connecting makes no request: a scenario that takes
    a while to come up is waited out without leaving a trail of spans in the
    report of the very telemetry the run is there to measure.
    """
    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if wait_for_port(port, timeout=_POLL_INTERVAL_SECONDS):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            wait_for_health(base_url, timeout=remaining)
            return
        # After the check, so a scenario that binds and exits in the same
        # instant is reported as having exited rather than as never binding.
        if process.poll() is not None:
            raise RuntimeError(
                f"the server scenario {list(command)} exited with "
                f"{process.returncode} before it listened on {base_url}"
            )
    raise RuntimeError(
        f"the server scenario {list(command)} did not listen on {base_url} "
        f"within {_STARTUP_TIMEOUT_SECONDS}s"
    )


def _stop(process: subprocess.Popen[bytes]) -> int:
    """Close standard input and wait, so the scenario flushes what it emitted.

    Its exit code is this process's: the runner reads a scenario's result from
    the command it started, and that command is this one.
    """
    if process.stdin is not None:
        process.stdin.close()
    try:
        return process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        raise RuntimeError(
            "the server scenario did not exit within "
            f"{_SHUTDOWN_TIMEOUT_SECONDS}s of its standard input closing; "
            "a scenario shuts down on EOF so its SDK can flush"
        ) from None


if __name__ == "__main__":
    sys.exit(main())
