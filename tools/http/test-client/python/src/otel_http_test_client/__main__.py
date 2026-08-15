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
import contextlib
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
# A killed process is gone in an instant unless it is stuck in the kernel, so
# this is only there to stop cleanup outlasting the failure it is cleaning up
# after.
_REAP_TIMEOUT_SECONDS = 10

# Windows has no process groups to inherit, so a new one has to be asked for
# at creation; POSIX gets the same isolation from ``start_new_session``.
if sys.platform == "win32":
    _NEW_PROCESS_GROUP = subprocess.CREATE_NEW_PROCESS_GROUP
else:
    _NEW_PROCESS_GROUP = 0


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

    if bool(arguments.url) == bool(arguments.serve):
        parser.error("give either a base URL or --serve COMMAND, not both")

    if arguments.url:
        wait_for_health(arguments.url)
        drive(arguments.url)
        return 0
    return _serve_and_drive(arguments.serve)


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
        creationflags=_NEW_PROCESS_GROUP,
    )

    try:
        _wait_for_start(process, port, base_url, command)
        drive(base_url)
    except BaseException:
        _kill_tree(process)
        raise

    return _stop(process)


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    """Kill the scenario and whatever it started, then reap it.

    A scenario only reaches here when it did not stop on its own, so killing
    the command alone can leave the real server alive: still holding the port
    the next run wants, and still holding the output pipe the runner reads
    until this process's own timeout is hit rather than the scenario's.

    Every step is bounded and nothing here raises, because the caller has a
    precise reason for this scenario's failure to report and waiting on
    cleanup would replace it with the runner's much later, vaguer one.
    """
    if process.poll() is None:
        try:
            if sys.platform == "win32":
                _kill_windows_tree(process.pid)
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            # The kill would not run, or ran and reported that it did not
            # kill; the direct child is still killable either way, and one
            # that has already gone makes this a no-op.
            process.kill()
    try:
        process.wait(timeout=_REAP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=_REAP_TIMEOUT_SECONDS)


def _kill_windows_tree(pid: int) -> None:
    """Kill a tree the way Windows offers, since its groups are not killable.

    Resolved rather than found on ``PATH`` so this cannot run something else
    that happens to be named ``taskkill``, and checked so that a ``taskkill``
    which ran and refused is a failure the caller can fall back from rather
    than silence.
    """
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    subprocess.run(  # noqa: S603
        [
            os.path.join(system_root, "System32", "taskkill.exe"),
            "/PID",
            str(pid),
            "/T",
            "/F",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


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
