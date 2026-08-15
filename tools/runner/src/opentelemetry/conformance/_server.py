# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A server the scenarios run against, started for the session.

Scenarios reach it through a base URL in their environment, so canned
responses replace cassette replay without tying conformance to one language.
What to run is declared, not built in: any command that serves HTTP and
answers a health endpoint.
"""

from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from string import Template
from types import TracebackType
from typing import IO

from ._env import timeout_seconds

# Overridable through the environment; see ``timeout_seconds``.
_STARTUP_TIMEOUT = ("OTEL_CONFORMANCE_SERVER_STARTUP_TIMEOUT", 30.0)
_STOP_TIMEOUT = ("OTEL_CONFORMANCE_SERVER_STOP_TIMEOUT", 10.0)
_POLL_INTERVAL_SECONDS = 0.1


class Server:
    """Runs a declared command for the session and waits for it to answer.

    The command is told which port to listen on through ``${PORT}`` and
    inherits this process's environment; anything else it needs it carries
    itself, e.g. ``env VAR=value the-server --port ${PORT}``.
    """

    def __init__(
        self, command: tuple[str, ...], *, health_path: str = "/health"
    ) -> None:
        # The socket is held open until the child is spawned; releasing it
        # here would leave the port free for a parallel run to take.
        self._reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._reservation.bind(("127.0.0.1", 0))
        self._port = int(self._reservation.getsockname()[1])
        self._command = tuple(
            Template(part).safe_substitute(PORT=str(self._port))
            for part in command
        )
        self._health_path = health_path
        self._process: subprocess.Popen[bytes] | None = None
        # A file rather than a pipe: nothing drains the output until something
        # goes wrong, and a full pipe buffer would wedge a chatty server.
        self._log: IO[bytes] | None = None
        self._log_path: Path | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    def start(self) -> Server:
        descriptor, name = tempfile.mkstemp(
            prefix="otel-conformance-server-", suffix=".log"
        )
        os.close(descriptor)
        self._log_path = Path(name)
        self._log = self._log_path.open("wb")
        self._release_reservation()
        # Its own process group, so stopping it reaches the server and not
        # just a wrapper — `env VAR=value the-server` or a shell one-liner
        # would otherwise leave the real server holding the port.
        self._process = subprocess.Popen(  # noqa: S603
            list(self._command),
            stdout=self._log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            self._wait_for_ready()
        except BaseException:
            self.close()
            raise
        return self

    def _release_reservation(self) -> None:
        self._reservation.close()

    def _wait_for_ready(self) -> None:
        startup = timeout_seconds(*_STARTUP_TIMEOUT)
        deadline = time.monotonic() + startup
        while time.monotonic() < deadline:
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(
                    f"Server {self._command} exited with "
                    f"{self._process.returncode}\n{self._output()}"
                )
            if self._is_ready():
                return
            time.sleep(_POLL_INTERVAL_SECONDS)
        raise RuntimeError(
            f"Server {self._command} did not become ready within "
            f"{startup}s on {self.url}\n{self._output()}"
        )

    def _is_ready(self) -> bool:
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"{self.url}{self._health_path}", timeout=1
            ) as response:
                return response.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    def _signal(self, number: int) -> None:
        """Signal the whole group the server was started in.

        A group so a wrapper command passes it on; falling back to the direct
        child covers a group that has already gone, and Windows, where there
        is no group to signal.
        """
        process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(process.pid), number)
        except (AttributeError, OSError):
            process.send_signal(number)

    def _output(self) -> str:
        if self._log is None or self._log_path is None:
            return ""
        self._log.flush()
        return self._log_path.read_text(encoding="utf-8", errors="replace")

    def close(self) -> None:
        self._release_reservation()  # a no-op once start() released it
        if self._process is not None:
            self._signal(signal.SIGTERM)
            try:
                self._process.wait(timeout=timeout_seconds(*_STOP_TIMEOUT))
            except subprocess.TimeoutExpired:
                # Windows has no SIGKILL; SIGTERM there is already a kill.
                self._signal(getattr(signal, "SIGKILL", signal.SIGTERM))
                self._process.wait()
            self._process = None
        if self._log is not None:
            self._log.close()
            self._log = None
        if self._log_path is not None:
            # A grandchild can still hold the handle just after the server
            # exits, which on Windows fails the unlink. A file left in the
            # system temp directory is not worth failing a run over.
            with contextlib.suppress(PermissionError):
                self._log_path.unlink(missing_ok=True)
            self._log_path = None

    def __enter__(self) -> Server:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
