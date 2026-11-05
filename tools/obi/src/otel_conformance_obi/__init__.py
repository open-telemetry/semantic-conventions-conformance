# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-obi``: runs a scenario under OpenTelemetry eBPF
Instrumentation.

OBI instruments a process from outside it, so the scenario program carries no
OpenTelemetry at all and the run command wraps it instead of preloading an
agent into it. Two subcommands:

``install [-- COMMAND...]``
    What a package's ``setup:`` runs. Downloads the pinned OBI release into
    the cache, then runs ``COMMAND`` — the scenario's own build step — so a
    single ``setup:`` covers both.

``run [--exe GLOB] [--args GLOB] COMMAND...``
    What a scenario's ``run:`` runs. Starts ``COMMAND`` with
    ``OTEL_CONFORMANCE_GATE`` naming a named pipe, waits for the scenario to
    reach it before its workload, starts OBI selecting processes by
    executable path and command line (by default ``COMMAND``'s own
    executable), releases the scenario once OBI's ``instrumented_processes``
    metric counts it, keeps OBI running for a settle period after ``COMMAND``
    exits so its exporters flush, then stops it. Exits with ``COMMAND``'s
    status, or fails when OBI exits before it is stopped.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Mapping, Sequence

INSTALL = "install"

RUN = "run"

BINARY = "obi"

RELEASES = (
    "https://github.com/open-telemetry/opentelemetry-ebpf-instrumentation"
    "/releases/download"
)

BINARY_VARIABLE = "OTEL_CONFORMANCE_OBI_BINARY"

READY_TIMEOUT_VARIABLE = "OTEL_CONFORMANCE_OBI_READY_TIMEOUT"

SETTLE_VARIABLE = "OTEL_CONFORMANCE_OBI_SETTLE"

GATE_VARIABLE = "OTEL_CONFORMANCE_GATE"

POLL_INTERVAL = 0.05

CONFIG_VARIABLE = "OTEL_CONFORMANCE_OBI_CONFIG"

CONFIG = "obi.yaml"

GATE_RELEASE = b"1"

DEFAULT_READY_TIMEOUT = 45.0

METRIC_EXPORT_INTERVAL_MILLIS = 1000

DEFAULT_SETTLE = 3.0

STOP_TIMEOUT = 30.0

INSTRUMENTED_PROCESSES = re.compile(
    r"^obi_instrumented_processes\{[^}]*"
    r'process_executable_name="(?P<name>[^"]*)"[^}]*\}\s+(?P<value>\S+)$',
    re.MULTILINE,
)

ARCHITECTURES = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
}

PIN = re.compile(
    r"^OBI_LINUX_(?P<arch>[A-Z0-9]+)="
    r"(?P<release>[^\s@]+)@sha256:(?P<digest>[0-9a-f]{64})$",
    re.MULTILINE,
)

GLOB_SPECIALS = re.compile(r"([*?\\\[\]{}])")

WATCHDOG = """\
exec 3<&0
"$0" -config "$1" </dev/null 3<&- &
obi=$!
(cat <&3; kill -TERM "$obi"; sleep "$2"; kill -KILL "$obi") >/dev/null 2>&1 &
watch=$!
exec 3<&-
wait "$obi"
status=$?
kill "$watch" 2>/dev/null
exit "$status"
"""

REAPER = """\
import os, signal, sys
if sys.stdin.buffer.read() != b"done\\n":
    try:
        os.killpg(int(sys.argv[1]), signal.SIGKILL)
    except ProcessLookupError:
        pass
"""

REAPER_DONE = b"done\n"


class LauncherError(RuntimeError):
    """OBI could not be installed, started, or attached."""


def pins(text: str | None = None) -> dict[str, tuple[str, str]]:
    if text is None:
        text = (
            Path(__file__)
            .with_name("versions.env")
            .read_text(encoding="utf-8")
        )
    found = {
        match["arch"].lower(): (match["release"], match["digest"])
        for match in PIN.finditer(text)
    }
    if not found:
        raise LauncherError("versions.env pins no OBI release")
    return found


def pin(arch: str) -> tuple[str, str]:
    try:
        return pins()[arch]
    except KeyError:
        raise LauncherError(
            f"versions.env pins no OBI build for {arch}"
        ) from None


def version() -> str:
    return pin(architecture())[0]


def architecture(machine: str | None = None) -> str:
    machine = (machine or platform.machine()).lower()
    try:
        return ARCHITECTURES[machine]
    except KeyError:
        raise LauncherError(f"OBI publishes no build for {machine}") from None


def archive_url(release: str, arch: str) -> str:
    return f"{RELEASES}/{release}/obi-{release}-linux-{arch}.tar.gz"


def cache_dir(release: str, environ: Mapping[str, str] = os.environ) -> Path:
    root = environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(root) / "otel-conformance" / "obi" / release


def binary(environ: Mapping[str, str] = os.environ) -> Path:
    override = environ.get(BINARY_VARIABLE)
    if override:
        return Path(override).absolute()
    return cache_dir(version(), environ) / BINARY


def check_host() -> None:
    if not sys.platform.startswith("linux"):
        raise LauncherError("OBI runs on Linux only")
    if os.geteuid() == 0:
        return
    try:
        allowed = (
            subprocess.run(  # noqa: S603
                ["sudo", "-n", "true"],  # noqa: S607
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
    except OSError:
        allowed = False
    if not allowed:
        raise LauncherError(
            "OBI needs root: run as root or allow passwordless `sudo -n`"
        )


def install(environ: Mapping[str, str] = os.environ) -> Path:
    check_host()
    if environ.get(BINARY_VARIABLE):
        return binary(environ)
    arch = architecture()
    release, digest = pin(arch)
    target = cache_dir(release, environ) / BINARY
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    url = archive_url(release, arch)
    print(f"downloading {url}", file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as scratch:
        archive = Path(scratch) / "obi.tar.gz"
        staged = Path(scratch) / BINARY
        try:
            hasher = hashlib.sha256()
            with (
                urllib.request.urlopen(url) as response,  # noqa: S310
                archive.open("wb") as out,
            ):
                while chunk := response.read(1 << 16):
                    hasher.update(chunk)
                    out.write(chunk)
            if hasher.hexdigest() != digest:
                raise LauncherError(
                    f"{url} has SHA-256 {hasher.hexdigest()}, but "
                    f"versions.env pins {digest}"
                )
            with tarfile.open(archive) as bundle:
                source = bundle.extractfile(bundle.getmember(BINARY))
                if source is None:
                    raise KeyError(BINARY)
                with source, staged.open("wb") as out:
                    shutil.copyfileobj(source, out)
        except (urllib.error.URLError, OSError) as error:
            raise LauncherError(f"downloading {url}: {error}") from error
        except (tarfile.TarError, KeyError) as error:
            raise LauncherError(
                f"{url} holds no {BINARY} executable: {error}"
            ) from error
        staged.chmod(0o755)
        staged.replace(target)
    return target


def config_template(environ: Mapping[str, str] = os.environ) -> Path:
    override = environ.get(CONFIG_VARIABLE)
    return Path(override) if override else Path(__file__).with_name(CONFIG)


def glob_literal(text: str) -> str:
    return GLOB_SPECIALS.sub(r"\\\1", text)


def seconds(
    environ: Mapping[str, str], variable: str, default: float
) -> float:
    raw = environ.get(variable)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise LauncherError(
            f"{variable} must be a number of seconds, not {raw!r}"
        ) from None
    if value < 0:
        raise LauncherError(f"{variable} must not be negative, not {raw!r}")
    return value


def process_match(
    command: Sequence[str], exe: str | None = None, args: str | None = None
) -> dict[str, list[str]]:
    if exe is None and args is None:
        resolved = shutil.which(command[0])
        if resolved is None:
            raise LauncherError(
                f"{command[0]} could not be started: not found"
            )
        exe = glob_literal(os.path.realpath(resolved))
    match: dict[str, list[str]] = {}
    if exe is not None:
        match["exe_path_glob"] = [exe]
    if args is not None:
        match["cmd_args_glob"] = [args]
    return match


def render_config(
    template: str,
    selector: Mapping[str, list[str]],
    metrics_port: int,
    environ: Mapping[str, str],
    launcher: Sequence[int] = (),
) -> str:
    endpoint = environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        raise LauncherError("OTEL_EXPORTER_OTLP_ENDPOINT is not set")
    protocol = environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    if protocol != "grpc":
        raise LauncherError(f"OBI scenarios export over grpc, not {protocol}")
    values = {
        "OBI_PROCESS_MATCH": json.dumps(dict(selector)),
        "OBI_LAUNCHER_PIDS": json.dumps(list(launcher)),
        "OBI_INTERNAL_METRICS_PORT": str(metrics_port),
        "OTEL_EXPORTER_OTLP_ENDPOINT": endpoint,
        "OBI_METRIC_EXPORT_INTERVAL": str(METRIC_EXPORT_INTERVAL_MILLIS),
    }

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            raise LauncherError(f"{CONFIG} references unknown variable {name}")
        return values[name]

    return re.sub(r"\$\{([A-Z0-9_]+)\}", substitute, template)


def instrumented(exposition: str, executable: str) -> bool:
    for sample in INSTRUMENTED_PROCESSES.finditer(exposition):
        if sample["name"] != executable:
            continue
        try:
            if float(sample["value"]) > 0:
                return True
        except ValueError:
            continue
    return False


def lineage(pid: int | None = None) -> list[int]:
    pid = os.getpid() if pid is None else pid
    found: list[int] = []
    while pid > 1:
        found.append(pid)
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        except OSError:
            break
        pid = int(stat.rsplit(")", 1)[1].split()[1])
    return found


def gate_holder(gate: Path) -> int | None:
    target = os.path.realpath(gate)
    own = os.getpid()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) == own:
            continue
        try:
            descriptors = list((entry / "fd").iterdir())
        except OSError:
            continue
        for descriptor in descriptors:
            try:
                if os.readlink(descriptor) == target:
                    return int(entry.name)
            except OSError:
                continue
    return None


def executable_name(pid: int) -> str:
    try:
        return Path(os.readlink(f"/proc/{pid}/exe")).name
    except OSError as error:
        raise LauncherError(
            f"reading the executable of the scenario process {pid}: {error}"
        ) from error


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _scrape(port: int) -> str:
    try:
        with urllib.request.urlopen(  # noqa: S310
            f"http://127.0.0.1:{port}/metrics", timeout=1
        ) as response:
            return response.read().decode(errors="replace")
    except (urllib.error.URLError, OSError):
        return ""


def _privileged(command: list[str]) -> list[str]:
    return command if os.geteuid() == 0 else ["sudo", "-n", *command]


def obi_command(executable: Path, config: Path) -> list[str]:
    return _privileged(
        [
            "sh",
            "-c",
            WATCHDOG,
            str(executable),
            str(config),
            f"{STOP_TIMEOUT:g}",
        ]
    )


def exit_status(code: int) -> int:
    return 128 - code if code < 0 else code


class Scenario:
    def __init__(self, command: Sequence[str], gate: Path) -> None:
        os.mkfifo(gate, 0o600)
        self._path = gate
        self._gate: int | None = None
        try:
            self.process = subprocess.Popen(  # noqa: S603
                list(command),
                env={**os.environ, GATE_VARIABLE: str(gate)},
                start_new_session=True,
            )
        except OSError as error:
            raise LauncherError(
                f"{command[0]} could not be started: {error}"
            ) from error
        self._reaper = subprocess.Popen(  # noqa: S603
            [sys.executable, "-I", "-c", REAPER, str(self.process.pid)],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def stand_down(self) -> None:
        if self._reaper.stdin is not None and not self._reaper.stdin.closed:
            try:
                self._reaper.stdin.write(REAPER_DONE)
                self._reaper.stdin.close()
            except BrokenPipeError:
                pass
        self._reaper.wait()

    def status(self) -> int | None:
        code = self.process.poll()
        return None if code is None else exit_status(code)

    def wait_at_gate(self, deadline: float, timeout: float) -> None:
        while self._gate is None:
            try:
                self._gate = os.open(self._path, os.O_WRONLY | os.O_NONBLOCK)
            except OSError as error:
                if error.errno != errno.ENXIO:
                    raise LauncherError(
                        f"opening the gate {self._path}: {error}"
                    ) from error
                status = self.status()
                if status is not None:
                    raise LauncherError(
                        f"the scenario exited with status {status} before "
                        f"reaching the gate in {GATE_VARIABLE}"
                    ) from None
                if time.monotonic() > deadline:
                    raise LauncherError(
                        f"the scenario did not reach the gate in "
                        f"{GATE_VARIABLE} within {timeout:g}s"
                    ) from None
                time.sleep(POLL_INTERVAL)

    def release(self) -> None:
        if self._gate is not None:
            try:
                os.write(self._gate, GATE_RELEASE)
            except BrokenPipeError:
                pass
        self.close_gate()

    def close_gate(self) -> None:
        if self._gate is not None:
            os.close(self._gate)
            self._gate = None

    def _signal_group(self, signum: int) -> None:
        try:
            os.killpg(self.process.pid, signum)
        except ProcessLookupError:
            pass

    def signal(self, signum: int) -> None:
        if self.process.poll() is None:
            self._signal_group(signum)

    def kill(self) -> None:
        self._signal_group(signal.SIGKILL)
        self.process.wait()
        self.close_gate()


def _wait_ready(
    obi: subprocess.Popen[bytes],
    scenario: Scenario,
    metrics_port: int,
    executable: str,
    deadline: float,
    timeout: float,
) -> None:
    while not instrumented(_scrape(metrics_port), executable):
        time.sleep(POLL_INTERVAL)
        if obi.poll() is not None:
            raise LauncherError(
                f"OBI exited with status {obi.returncode} before instrumenting"
            )
        status = scenario.status()
        if status is not None:
            raise LauncherError(
                f"the scenario exited with status {status} before OBI "
                "instrumented it"
            )
        if time.monotonic() > deadline:
            raise LauncherError(
                f"OBI did not instrument the scenario within {timeout:g}s"
            )


def _stop(obi: subprocess.Popen[bytes]) -> None:
    if obi.stdin is not None:
        obi.stdin.close()
    try:
        obi.wait(STOP_TIMEOUT + 5)
    except subprocess.TimeoutExpired:
        obi.kill()
        obi.wait()


def run(
    command: Sequence[str],
    exe: str | None = None,
    args: str | None = None,
    environ: Mapping[str, str] = os.environ,
) -> int:
    if not sys.platform.startswith("linux"):
        raise LauncherError("OBI runs on Linux only")
    if not command:
        raise LauncherError("run needs the scenario command")
    selector = process_match(command, exe, args)
    executable = binary(environ)
    if not executable.is_file():
        raise LauncherError(
            f"{executable} is missing — `otel-conformance-obi install` fetches it"
        )
    ready_timeout = seconds(
        environ, READY_TIMEOUT_VARIABLE, DEFAULT_READY_TIMEOUT
    )
    settle = seconds(environ, SETTLE_VARIABLE, DEFAULT_SETTLE)
    template = config_template(environ).read_text(encoding="utf-8")

    scenario: Scenario | None = None
    forwarded = (signal.SIGINT, signal.SIGTERM)
    previous = {signum: signal.getsignal(signum) for signum in forwarded}

    def forward(signum: int, _frame: object) -> None:
        if scenario is not None and scenario.status() is None:
            scenario.signal(signum)
            return
        handler = previous[signal.Signals(signum)]
        signal.signal(signum, signal.SIG_DFL if handler is None else handler)
        signal.raise_signal(signum)

    for signum in forwarded:
        signal.signal(signum, forward)
    obi: subprocess.Popen[bytes] | None = None
    try:
        with tempfile.TemporaryDirectory() as scratch:
            try:
                deadline = time.monotonic() + ready_timeout
                gate = Path(scratch) / "gate"
                scenario = Scenario(command, gate)
                scenario.wait_at_gate(deadline, ready_timeout)
                holder = gate_holder(gate)
                if holder is None:
                    raise LauncherError(
                        "no process holds the gate open, though the scenario "
                        "reached it"
                    )
                waiting = executable_name(holder)
                metrics_port = free_port()
                config = Path(scratch) / "obi.yaml"
                config.write_text(
                    render_config(
                        template, selector, metrics_port, environ, lineage()
                    ),
                    encoding="utf-8",
                )
                sys.stderr.flush()
                obi = subprocess.Popen(  # noqa: S603
                    obi_command(executable, config),
                    stdin=subprocess.PIPE,
                    stdout=sys.stderr,
                    stderr=sys.stderr,
                )
                _wait_ready(
                    obi,
                    scenario,
                    metrics_port,
                    waiting,
                    deadline,
                    ready_timeout,
                )
                scenario.release()
                status = exit_status(scenario.process.wait())
                settled = time.monotonic() + settle
                while time.monotonic() < settled and obi.poll() is None:
                    time.sleep(POLL_INTERVAL)
                if obi.poll() is not None:
                    raise LauncherError(
                        f"OBI exited with status {obi.returncode} while the "
                        f"scenario ran (the scenario exited with status "
                        f"{status})"
                    )
                _stop(obi)
                return status
            except BaseException:
                if scenario is not None:
                    scenario.kill()
                if obi is not None:
                    _stop(obi)
                raise
    finally:
        if scenario is not None:
            scenario.stand_down()
        for signum, handler in previous.items():
            signal.signal(
                signum, signal.SIG_DFL if handler is None else handler
            )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-obi",
        description=(__doc__ or "").splitlines()[0],
    )
    commands = parser.add_subparsers(dest="action", required=True)
    install_parser = commands.add_parser(
        INSTALL, help="fetch the pinned OBI release, then run COMMAND"
    )
    install_parser.add_argument("command", nargs=argparse.REMAINDER)
    run_parser = commands.add_parser(RUN, help="run COMMAND under OBI")
    run_parser.add_argument(
        "--exe",
        help="glob on the resolved executable path of the process to instrument",
    )
    run_parser.add_argument(
        "--args",
        help="glob on the command line, without argv[0], of the process to "
        "instrument",
    )
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def _strip_separator(command: Sequence[str]) -> list[str]:
    command = list(command)
    return command[1:] if command[:1] == ["--"] else command


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    command = _strip_separator(arguments.command)
    try:
        if arguments.action == INSTALL:
            install()
            if not command:
                return 0
            try:
                return subprocess.call(command)  # noqa: S603
            except OSError as error:
                raise LauncherError(f"{command[0]}: {error}") from error
        return run(command, arguments.exe, arguments.args)
    except LauncherError as error:
        print(f"otel-conformance-obi: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
