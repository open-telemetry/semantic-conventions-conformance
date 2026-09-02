# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-http-drive`` sends the HTTP contract to a measured server."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

import yaml

from . import (
    ACTIONS_VARIABLE,
    PORT_VARIABLE,
    PROTOCOL_VARIABLE,
    Exchange,
    _action_table,  # pyright: ignore[reportPrivateUsage]
    _drive_exchanges,  # pyright: ignore[reportPrivateUsage]
    _wait_for_health_exchange,  # pyright: ignore[reportPrivateUsage]
    request,
    reserve_port,
    verify,
    wait_for_port,
)
from . import (
    _exchange_from_action as _decode_action,  # pyright: ignore[reportPrivateUsage]
)

_PROTOCOL_VERSION = "jsonl-v1"

# A cold runtime with instrumentation enabled can take a while to answer.
_STARTUP_TIMEOUT_SECONDS = 60
_SHUTDOWN_TIMEOUT_SECONDS = 30
_POLL_INTERVAL_SECONDS = 0.1


def _contract_path() -> Path:
    packaged = Path(__file__).parent / "contract.yaml"
    if packaged.is_file():
        return packaged
    return Path(__file__).resolve().parents[3] / "contract.yaml"


def _load_contract() -> tuple[Exchange, ...]:
    path = _contract_path()
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = [document["readiness"], *document["scenarios"]]
    exchanges: list[Exchange] = []
    for index, entry in enumerate(entries):
        exchange = _decode_action(
            entry["action"],
            variable=f"{path} entry {index}",
            readiness=index == 0,
        )
        exchanges.append(exchange._replace(description=entry["description"]))
    return tuple(exchanges)


_DRIVER_EXCHANGES = _load_contract()


def _selected_exchanges() -> tuple[Exchange, ...]:
    """The action table this run is driven by, readiness first.

    The runner parses the contract the package declares and passes the whole
    table down, so a package pointing at its own contract file is driven by
    that file rather than by whichever one this installation happens to ship.
    The packaged contract is the fallback for driving a server by hand.

    A malformed table fails here, before a measured server is started with it.
    """

    if os.environ.get(ACTIONS_VARIABLE) is None:
        return _DRIVER_EXCHANGES
    return _action_table()


def wait_for_health(base_url: str, timeout: float = 30.0) -> None:
    """Check the canonical readiness exchange used by the driver."""
    _wait_for_health_exchange(base_url, _selected_exchanges()[0], timeout)


if sys.platform == "win32":
    _CREATE_SUSPENDED = 0x00000004
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


def _driven_protocol() -> str | None:
    """The protocol the runner is driving this process with, if any.

    Set only for a persistent run, so its absence is what makes a manual
    ``--serve`` one-shot. An unknown value is a runner this driver cannot
    speak to, which fails before a measured server is started.
    """

    protocol = os.environ.get(PROTOCOL_VARIABLE)
    if protocol is None or protocol == "":
        return None
    if protocol != _PROTOCOL_VERSION:
        raise SystemExit(
            f"{PROTOCOL_VARIABLE}={protocol!r} is not a protocol this driver "
            f"speaks; expected {_PROTOCOL_VERSION!r}"
        )
    return protocol


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
        "--persistent",
        action="store_true",
        help=(
            "speak jsonl-v1 on stdin and stdout while serving COMMAND; the "
            f"runner sets ${{{PROTOCOL_VARIABLE}}} instead, so this is for "
            "driving a server by hand"
        ),
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
    persistent = arguments.persistent or _driven_protocol() is not None

    if arguments.url is None:
        if arguments.serve is None:
            parser.error("give either a base URL or --serve COMMAND")
        if not arguments.serve:
            parser.error("--serve requires COMMAND")
        return _serve_and_drive(arguments.serve, persistent=persistent)
    if arguments.serve is not None:
        parser.error("give either a base URL or --serve COMMAND, not both")
    if persistent:
        parser.error(
            "a persistent run requires --serve COMMAND; driving a base URL "
            "sends one pass and exits"
        )

    _wait_for_health_exchange(arguments.url, _selected_exchanges()[0])
    _drive_exchanges(arguments.url, _selected_exchanges()[1:])
    return 0


@dataclass
class _ProcessTree:
    process: subprocess.Popen[bytes]
    job: _WindowsJob | None

    def close_owner(self) -> None:
        if self.job is not None:
            self.job.close()
            self.job = None


class _WindowsJob:
    """A Windows Job Object that kills every child when its handle closes."""

    def __init__(self, handle: int, kernel32: Any) -> None:
        self._handle = handle
        self._kernel32 = kernel32

    @classmethod
    def assign_and_resume(
        cls, process: subprocess.Popen[bytes]
    ) -> _WindowsJob:
        if sys.platform != "win32":
            raise AssertionError(
                "Windows Job Objects are only available on Windows"
            )

        class _IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_ulonglong),
                ("WriteOperationCount", ctypes.c_ulonglong),
                ("OtherOperationCount", ctypes.c_ulonglong),
                ("ReadTransferCount", ctypes.c_ulonglong),
                ("WriteTransferCount", ctypes.c_ulonglong),
                ("OtherTransferCount", ctypes.c_ulonglong),
            ]

        class _BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class _ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", _BasicLimitInformation),
                ("IoInfo", _IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        win_dll = getattr(ctypes, "WinDLL")
        kernel32 = win_dll("kernel32", use_last_error=True)
        ntdll = win_dll("ntdll")
        kernel32.CreateJobObjectW.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        ntdll.NtResumeProcess.restype = ctypes.c_long

        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            _raise_windows_error("could not create a Job Object")
        job = cls(cast(int, handle), kernel32)
        try:
            limits = _ExtendedLimitInformation()
            limits.BasicLimitInformation.LimitFlags = (
                _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )
            if not kernel32.SetInformationJobObject(
                handle,
                _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                _raise_windows_error("could not configure the Job Object")

            process_handle = cast(Any, process)._handle
            if not kernel32.AssignProcessToJobObject(handle, process_handle):
                _raise_windows_error(
                    "could not assign the server scenario to the Job Object"
                )
            status = ntdll.NtResumeProcess(process_handle)
            if status < 0:
                raise OSError(
                    f"could not resume the server scenario (NTSTATUS "
                    f"0x{status & 0xFFFFFFFF:08x})"
                )
            return job
        except BaseException:
            job.close()
            raise

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = 0


def _raise_windows_error(message: str) -> NoReturn:
    error = ctypes.get_last_error()
    raise OSError(error, f"{message}: {ctypes.FormatError(error).strip()}")


def _serve_and_drive(
    command: Sequence[str], *, persistent: bool = False
) -> int:
    """Run ``command`` as a server, drive it, and report how it exited."""
    exchanges = _selected_exchanges()
    port, reservation = reserve_port()
    base_url = f"http://127.0.0.1:{port}"
    env = {**os.environ, PORT_VARIABLE: str(port)}
    # Passed on exactly as it arrived when the runner set it, so the measured
    # server answers the table the run is driven by, character for character.
    if ACTIONS_VARIABLE not in env:
        env[ACTIONS_VARIABLE] = _canonical_action_table()

    reservation.close()
    tree = _start_process(command, env, persistent=persistent)
    process = tree.process
    last_sequence = 0
    previous_sigterm = None
    if sys.platform != "win32":
        previous_sigterm = signal.signal(signal.SIGTERM, _exit_on_signal)

    try:
        try:
            _wait_for_start(
                process,
                port,
                base_url,
                command,
                check_health=not persistent,
            )
            if persistent:
                last_sequence = _drive_persistent(
                    process, base_url, exchanges[0]
                )
            else:
                _drive_exchanges(base_url, exchanges[1:])
        except BaseException:
            _kill_tree(tree)
            raise

        result = _stop(tree)
        if persistent:
            _write_record("stopped", last_sequence + 1)
        return result
    finally:
        if previous_sigterm is not None:
            signal.signal(signal.SIGTERM, previous_sigterm)


def _start_process(
    command: Sequence[str],
    env: Mapping[str, str],
    *,
    persistent: bool,
) -> _ProcessTree:
    creationflags = _CREATE_SUSPENDED if sys.platform == "win32" else 0
    process = subprocess.Popen(  # noqa: S603
        list(command),
        stdin=subprocess.PIPE,
        stdout=sys.stderr if persistent else None,
        stderr=sys.stderr if persistent else None,
        env=env,
        start_new_session=sys.platform != "win32",
        creationflags=creationflags,
    )
    if sys.platform != "win32":
        return _ProcessTree(process, None)

    try:
        job = _WindowsJob.assign_and_resume(process)
    except BaseException:
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        process.wait()
        raise
    return _ProcessTree(process, job)


def _drive_persistent(
    process: subprocess.Popen[bytes], base_url: str, readiness: Exchange
) -> int:
    last_sequence = 0
    started_unix_nano = time.time_ns()
    status, response = _request_exchange(readiness, base_url)
    completed_unix_nano = time.time_ns()
    verify(readiness, status, response)
    _write_record(
        "ready",
        0,
        started_unix_nano=started_unix_nano,
        completed_unix_nano=completed_unix_nano,
    )

    failed = False
    for raw in sys.stdin:
        if failed:
            continue
        expected = last_sequence + 1
        try:
            record = _parse_action_record(raw, expected)
            exchange = _exchange_from_action(record["action"])
            if process.poll() is not None:
                raise RuntimeError(
                    f"the server scenario exited with {process.returncode} "
                    "before the request"
                )
            started_unix_nano = time.time_ns()
            status, response = _request_exchange(exchange, base_url)
            completed_unix_nano = time.time_ns()
            verify(exchange, status, response)
        except Exception as error:
            last_sequence = expected
            _write_record("action_error", expected, error=_diagnostic(error))
            failed = True
            continue

        last_sequence = expected
        print(
            f"{exchange.method} {exchange.path} -> {status} {response[:60]}",
            file=sys.stderr,
            flush=True,
        )
        _write_record(
            "action_complete",
            expected,
            started_unix_nano=started_unix_nano,
            completed_unix_nano=completed_unix_nano,
        )
    return last_sequence


def _parse_action_record(raw: str, expected: int) -> Mapping[str, object]:
    try:
        loaded: object = json.loads(
            raw, parse_constant=lambda value: _reject_json_constant(value)
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"malformed jsonl-v1 action: {error}") from error
    if not isinstance(loaded, dict):
        raise ValueError("jsonl-v1 action must be a JSON object")
    record = cast(dict[str, object], loaded)
    if record.get("version") != _PROTOCOL_VERSION:
        raise ValueError(
            f"expected protocol version {_PROTOCOL_VERSION!r}, got "
            f"{record.get('version')!r}"
        )
    if record.get("type") != "action":
        raise ValueError(
            f"expected action sequence {expected}, got type "
            f"{record.get('type')!r}"
        )
    sequence = record.get("sequence")
    if (
        not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence != expected
    ):
        raise ValueError(
            f"expected action sequence {expected}, got {sequence!r}"
        )
    if not isinstance(record.get("action"), dict):
        raise ValueError("action must be a JSON object")
    return record


def _exchange_from_action(value: object) -> Exchange:
    """One action record's exchange, decoded the one canonical way.

    The shared decoder is what every workload in this package already uses,
    so a driver validating actions its own way could accept traffic no
    workload would, or refuse traffic every workload accepts.
    """

    return _decode_action(value, variable="jsonl-v1", readiness=False)


def _request_exchange(
    exchange: Exchange,
    base_url: str,
) -> tuple[int, str]:
    """Send one contract exchange exactly as the contract describes it.

    Nothing is added to what the action declares. A ``traceparent`` the
    driver invented would make the measured server a child of a remote
    parent, which changes the root of the trace, the sampling decision it
    inherits, and whether the server extracts context at all. The runner
    attributes telemetry by timestamp instead.
    """

    return request(
        exchange.method,
        f"{base_url}{exchange.path}",
        exchange.body,
    )


def _canonical_action_table() -> str:
    actions: list[dict[str, object]] = []
    for exchange in _DRIVER_EXCHANGES:
        request_document: dict[str, object] = {
            "method": exchange.method,
            "path": exchange.path,
        }
        if exchange.body is not None:
            request_document["body"] = exchange.body
        actions.append(
            {
                "request": request_document,
                "response": {
                    "body": exchange.response_body,
                    "status": exchange.status,
                },
            }
        )
    return json.dumps(
        actions,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _write_record(record_type: str, sequence: int, **fields: object) -> None:
    record = {
        "version": _PROTOCOL_VERSION,
        "type": record_type,
        "sequence": sequence,
        **fields,
    }
    print(
        json.dumps(
            record,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        flush=True,
    )


def _diagnostic(error: BaseException) -> str:
    detail = str(error) or type(error).__name__
    return f"{type(error).__name__}: {detail}"


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"invalid JSON constant {value}")


def _exit_on_signal(signum: int, _frame: object) -> NoReturn:
    raise SystemExit(128 + signum)


def _kill_tree(tree: _ProcessTree) -> None:
    """Kill the server command and every descendant, then reap it."""
    process = tree.process
    if process.poll() is None:
        if tree.job is not None:
            tree.close_owner()
        else:
            try:
                getpgid = getattr(os, "getpgid")
                killpg = getattr(os, "killpg")
                sigkill = getattr(signal, "SIGKILL")
                killpg(getpgid(process.pid), sigkill)
            except (AttributeError, OSError):
                process.kill()
    process.wait()
    tree.close_owner()


def _wait_for_start(
    process: subprocess.Popen[bytes],
    port: int,
    base_url: str,
    command: Sequence[str],
    *,
    check_health: bool = True,
) -> None:
    """Wait for the scenario to answer, or say why it never will."""
    deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if wait_for_port(port, timeout=_POLL_INTERVAL_SECONDS):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if check_health:
                wait_for_health(base_url, timeout=remaining)
            return
        if process.poll() is not None:
            raise RuntimeError(
                f"the server scenario {list(command)} exited with "
                f"{process.returncode} before it listened on {base_url}"
            )
    raise RuntimeError(
        f"the server scenario {list(command)} did not listen on {base_url} "
        f"within {_STARTUP_TIMEOUT_SECONDS}s"
    )


def _stop(tree: _ProcessTree) -> int:
    """Close child stdin once and wait for its SDK and server to flush."""
    process = tree.process
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()
    try:
        result = process.wait(timeout=_SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _kill_tree(tree)
        raise RuntimeError(
            "the server scenario did not exit within "
            f"{_SHUTDOWN_TIMEOUT_SECONDS}s of its standard input closing; "
            "a scenario shuts down on EOF so its SDK can flush"
        ) from None
    tree.close_owner()
    return result


if __name__ == "__main__":
    sys.exit(main())
