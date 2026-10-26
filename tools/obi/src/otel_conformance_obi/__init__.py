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

DEFAULT_READY_TIMEOUT = 60.0

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


class LauncherError(RuntimeError):
    """OBI could not be installed, started, or attached."""


def version() -> str:
    pins = Path(__file__).with_name("versions.env").read_text(encoding="utf-8")
    match = re.search(r"^OBI_VERSION=(\S+)$", pins, re.MULTILINE)
    if match is None:
        raise LauncherError("versions.env pins no OBI_VERSION")
    return match.group(1)


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
        return Path(override)
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
    release = version()
    target = cache_dir(release, environ) / BINARY
    if target.is_file():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    url = archive_url(release, architecture())
    print(f"downloading {url}", file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as scratch:
        archive = Path(scratch) / "obi.tar.gz"
        staged = Path(scratch) / BINARY
        try:
            with (
                urllib.request.urlopen(url) as response,  # noqa: S310
                archive.open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
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


def process_match(
    command: Sequence[str], exe: str | None = None, args: str | None = None
) -> dict[str, list[str]]:
    if exe is None and args is None:
        resolved = shutil.which(command[0])
        if resolved is None:
            raise LauncherError(
                f"{command[0]} could not be started: not found"
            )
        exe = os.path.realpath(resolved)
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
) -> str:
    endpoint = environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        raise LauncherError("OTEL_EXPORTER_OTLP_ENDPOINT is not set")
    protocol = environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    if protocol != "grpc":
        raise LauncherError(f"OBI scenarios export over grpc, not {protocol}")
    values = {
        "OBI_PROCESS_MATCH": json.dumps(dict(selector)),
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


def instrumented(exposition: str) -> bool:
    for sample in INSTRUMENTED_PROCESSES.finditer(exposition):
        try:
            if float(sample["value"]) > 0:
                return True
        except ValueError:
            continue
    return False


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


def obi_command(executable: Path, config: Path) -> list[str]:
    command = [str(executable), "-config", str(config)]
    if os.geteuid() != 0:
        command = ["sudo", "-n", *command]
    return command


def exit_status(code: int) -> int:
    return 128 - code if code < 0 else code


class Scenario:
    def __init__(self, command: Sequence[str], gate: Path) -> None:
        os.mkfifo(gate, 0o600)
        self._path = gate
        self._gate: int | None = None
        try:
            self.process = subprocess.Popen(  # noqa: S603
                list(command), env={**os.environ, GATE_VARIABLE: str(gate)}
            )
        except OSError as error:
            raise LauncherError(
                f"{command[0]} could not be started: {error}"
            ) from error

    def status(self) -> int | None:
        code = self.process.poll()
        return None if code is None else exit_status(code)

    def wait_at_gate(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while self._gate is None:
            try:
                self._gate = os.open(self._path, os.O_WRONLY | os.O_NONBLOCK)
            except OSError as error:
                if error.errno != errno.ENXIO:
                    raise
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
            os.close(self._gate)
            self._gate = None

    def signal(self, signum: int) -> None:
        if self.process.poll() is None:
            self.process.send_signal(signum)

    def kill(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        self.release()


def _wait_ready(
    obi: subprocess.Popen[bytes],
    scenario: Scenario,
    metrics_port: int,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while not instrumented(_scrape(metrics_port)):
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
    if obi.poll() is not None:
        return
    obi.send_signal(signal.SIGTERM)
    try:
        obi.wait(STOP_TIMEOUT)
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
    ready_timeout = float(
        environ.get(READY_TIMEOUT_VARIABLE, DEFAULT_READY_TIMEOUT)
    )
    settle = float(environ.get(SETTLE_VARIABLE, DEFAULT_SETTLE))
    template = config_template(environ).read_text(encoding="utf-8")

    scenario: Scenario | None = None

    def forward(signum: int, _frame: object) -> None:
        if scenario is not None:
            scenario.signal(signum)

    for forwarded in (signal.SIGINT, signal.SIGTERM):
        signal.signal(forwarded, forward)
    obi: subprocess.Popen[bytes] | None = None
    with tempfile.TemporaryDirectory() as scratch:
        try:
            scenario = Scenario(command, Path(scratch) / "gate")
            scenario.wait_at_gate(ready_timeout)
            metrics_port = free_port()
            config = Path(scratch) / "obi.yaml"
            config.write_text(
                render_config(template, selector, metrics_port, environ),
                encoding="utf-8",
            )
            sys.stderr.flush()
            obi = subprocess.Popen(  # noqa: S603
                obi_command(executable, config),
                stdin=subprocess.DEVNULL,
                stdout=sys.stderr,
                stderr=sys.stderr,
            )
            _wait_ready(obi, scenario, metrics_port, ready_timeout)
            scenario.release()
            status = exit_status(scenario.process.wait())
            deadline = time.monotonic() + settle
            while time.monotonic() < deadline and obi.poll() is None:
                time.sleep(POLL_INTERVAL)
            if obi.poll() is not None:
                raise LauncherError(
                    f"OBI exited with status {obi.returncode} while the "
                    "scenario ran"
                )
            _stop(obi)
            return status
        except BaseException:
            if scenario is not None:
                scenario.kill()
            if obi is not None:
                _stop(obi)
            raise


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
