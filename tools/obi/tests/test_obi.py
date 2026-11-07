# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import hashlib
import io
import os
import signal
import subprocess
import sys
import tarfile
import textwrap
import time
import urllib.error
from pathlib import Path

import pytest
import yaml

import otel_conformance_obi
from otel_conformance_obi import (
    BINARY_VARIABLE,
    CONFIG_VARIABLE,
    METRIC_EXPORT_INTERVAL_MILLIS,
    READY_TIMEOUT_VARIABLE,
    SETTLE_VARIABLE,
    LauncherError,
    architecture,
    archive_url,
    binary,
    cache_dir,
    check_host,
    config_template,
    exit_status,
    glob_literal,
    install,
    instrumented,
    lineage,
    main,
    pin,
    pins,
    process_match,
    render_config,
    run,
    seconds,
    version,
)

ENDPOINT = "http://127.0.0.1:4317"

MARKER = "gated-scenario"

SELECT_GATED = f"* {MARKER}"

FAKE_OBI = textwrap.dedent(
    """\
    import fnmatch, http.server, os, signal, sys, threading, time, yaml
    config = yaml.safe_load(open(sys.argv[sys.argv.index("-config") + 1]))
    obi = config["extensions"]["obi"]
    port = obi["daemon"]["internal_metrics"]["prometheus"]["port"]
    excluded = set()
    selector = {}
    for rule in obi["capture"]["rules"]:
        process = rule["match"]["process"]
        if rule["action"] == "exclude":
            excluded.update(process.get("target_pids", []))
        else:
            selector = process
    mode = os.environ.get("FAKE_OBI_MODE", "ready")
    open("obi.pid", "w").write(str(os.getpid()))
    print("fake obi on stdout", flush=True)
    print("fake obi on stderr", file=sys.stderr, flush=True)
    if mode == "die-early":
        sys.exit(3)
    attached = []

    class Metrics(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = "".join(
                f'obi_instrumented_processes{{process_executable_name="{name}"}} 1\\n'
                for name in attached
            ).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Metrics)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def matches(pid):
        try:
            exe = os.path.realpath(f"/proc/{pid}/exe")
            argv = open(f"/proc/{pid}/cmdline", "rb").read().decode().split("\\0")
        except OSError:
            return False
        args = " ".join(argv[1:]).strip()
        return all(
            fnmatch.fnmatchcase(value, selector[key][0])
            for key, value in (("exe_path_glob", exe), ("cmd_args_glob", args))
            if key in selector
        )

    if mode == "slow":
        time.sleep(0.5)
    found = None
    while found is None:
        for entry in sorted((name for name in os.listdir("/proc") if name.isdigit()), key=int, reverse=True):
            if entry.isdigit() and int(entry) not in (os.getpid(), os.getppid(), *excluded) and matches(entry):
                found = int(entry)
                break
        time.sleep(0.05)
    open("attached", "w").write(str(found))
    attached.append(os.path.basename(os.path.realpath(f"/proc/{found}/exe")))
    if mode == "die-later":
        while os.path.exists(f"/proc/{found}"):
            time.sleep(0.01)
        sys.exit(4)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    while True:
        time.sleep(0.05)
    """
)


GATED = textwrap.dedent(
    """\
    import os, pathlib, subprocess, sys, time
    pathlib.Path("scenario.pid").write_text(str(os.getpid()))
    time.sleep(float(os.environ.get("GATED_DELAY", "0")))
    with open(os.environ["OTEL_CONFORMANCE_GATE"], "rb") as gate:
        if gate.read() != b"1":
            sys.exit(98)
    pathlib.Path("released").write_text(str(os.getpid()))
    time.sleep(float(os.environ.get("GATED_LINGER", "0")))
    if os.environ.get("GATED_INTERRUPT_LAUNCHER"):
        subprocess.Popen(
            ["sh", "-c", f"sleep 0.5; kill -INT {os.getppid()}"],
            start_new_session=True,
        )
    attached = pathlib.Path("attached")
    instrumented = attached.exists() and attached.read_text() == str(os.getpid())
    sys.exit(int(sys.argv[1]) if instrumented else 99)
    """
)


def wait_for(*paths: Path, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while not all(path.exists() for path in paths):
        assert time.monotonic() < deadline, f"none of {paths} appeared"
        time.sleep(0.05)


def running_scripts(script: str) -> list[int]:
    alive: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if script.encode() in argv and running(int(entry.name), timeout=0.1):
            alive.append(int(entry.name))
    return alive


def gated_children() -> list[int]:
    return running_scripts(GATED)


def cleanup(tmp_path: Path, launched: subprocess.Popen[bytes]) -> None:
    for name in ("scenario.pid", "obi.pid"):
        try:
            os.kill(int((tmp_path / name).read_text()), signal.SIGKILL)
        except (OSError, ValueError):
            pass
    try:
        os.killpg(launched.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def launcher(
    tmp_path: Path, environ: dict[str, str], *command: str
) -> subprocess.Popen[bytes]:
    code = (
        "import sys, otel_conformance_obi as obi; "
        "obi._privileged = lambda command: command; "
        "sys.exit(obi.main(sys.argv[1:]))"
    )
    return subprocess.Popen(
        [sys.executable, "-c", code, "run", *command],
        cwd=tmp_path,
        env={**os.environ, **environ},
        start_new_session=True,
    )


def gated(status: int = 0) -> list[str]:
    return [sys.executable, "-c", GATED, str(status), MARKER]


def shell(command: list[str]) -> str:
    return " ".join(f"'{part}'" for part in command)


def running(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            stat = Path(f"/proc/{pid}/stat").read_text()
        except OSError:
            return False
        if stat.rsplit(")", 1)[1].split()[0] == "Z":
            return False
        time.sleep(0.05)
    return True


linux_only = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="OBI runs on Linux only"
)


def rendered(
    selector: dict[str, list[str]] | None = None,
    port: int = 9400,
    **environ: str,
) -> dict:
    environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", ENDPOINT)
    return yaml.safe_load(
        render_config(
            config_template({}).read_text(),
            selector or {"exe_path_glob": ["/srv/scenario"]},
            port,
            environ,
        )
    )


class TestTheHostCheck:
    @staticmethod
    def sudo(
        monkeypatch: pytest.MonkeyPatch, euid: int, status: int | None
    ) -> list[list[str]]:
        calls: list[list[str]] = []

        def fake_run(
            command: list[str], **_: object
        ) -> subprocess.CompletedProcess[bytes]:
            calls.append(command)
            if status is None:
                raise FileNotFoundError(command[0])
            return subprocess.CompletedProcess(command, status)

        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(
            otel_conformance_obi.os, "geteuid", lambda: euid, raising=False
        )
        monkeypatch.setattr(otel_conformance_obi.subprocess, "run", fake_run)
        return calls

    def test_another_platform_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")

        with pytest.raises(LauncherError, match="Linux only"):
            check_host()

    def test_root_needs_no_sudo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls = self.sudo(monkeypatch, euid=0, status=1)

        check_host()

        assert calls == []

    def test_passwordless_sudo_is_enough(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls = self.sudo(monkeypatch, euid=1000, status=0)

        check_host()

        assert calls == [["sudo", "-n", "true"]]

    @pytest.mark.parametrize("status", [1, None])
    def test_without_sudo_it_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, status: int | None
    ) -> None:
        self.sudo(monkeypatch, euid=1000, status=status)

        with pytest.raises(LauncherError, match="needs root"):
            check_host()

    def test_a_refused_host_runs_no_setup_command(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        marker = tmp_path / "ran"

        status = main(
            ["install", "--", "touch", str(marker)],
        )

        assert status == 1
        assert not marker.exists()
        assert "Linux only" in capsys.readouterr().err


class TestTheRelease:
    @pytest.fixture(autouse=True)
    def any_host(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(otel_conformance_obi, "check_host", lambda: None)

    def test_the_version_is_pinned(self) -> None:
        assert version().startswith("v")

    @pytest.mark.parametrize(
        ("machine", "arch"),
        [("x86_64", "amd64"), ("aarch64", "arm64"), ("arm64", "arm64")],
    )
    def test_the_machine_names_an_archive(
        self, machine: str, arch: str
    ) -> None:
        assert architecture(machine) == arch
        assert archive_url("v1.2.3", arch).endswith(
            "/v1.2.3/obi-v1.2.3-linux-" + arch + ".tar.gz"
        )

    def test_an_unsupported_machine_says_so(self) -> None:
        with pytest.raises(LauncherError, match="no build for riscv64"):
            architecture("riscv64")

    def test_the_binary_is_cached_per_version(self, tmp_path: Path) -> None:
        environ = {"XDG_CACHE_HOME": str(tmp_path)}

        assert (
            binary(environ)
            == tmp_path / "otel-conformance" / "obi" / version() / "obi"
        )
        assert (
            cache_dir("v9", environ)
            == tmp_path / "otel-conformance" / "obi" / "v9"
        )

    def test_an_explicit_binary_wins(self, tmp_path: Path) -> None:
        assert (
            binary({BINARY_VARIABLE: str(tmp_path / "obi")})
            == tmp_path / "obi"
        )

    def test_a_relative_binary_is_made_absolute(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.chdir(tmp_path)

        resolved = binary({BINARY_VARIABLE: "./obi"})

        assert resolved.is_absolute()
        assert resolved == tmp_path / "obi"

    def test_install_with_an_explicit_binary_runs_the_command(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv(BINARY_VARIABLE, str(tmp_path / "obi"))
        marker = tmp_path / "ran"

        status = main(
            [
                "install",
                "--",
                sys.executable,
                "-c",
                f"open({str(marker)!r}, 'w').close()",
            ]
        )

        assert status == 0
        assert marker.exists()

    def test_a_missing_setup_command_says_so(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(BINARY_VARIABLE, str(tmp_path / "obi"))

        assert main(["install", "--", str(tmp_path / "missing")]) == 1
        assert "missing" in capsys.readouterr().err

    def test_a_failed_download_says_so(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def refuse(url: str) -> None:
            raise urllib.error.URLError("no route")

        monkeypatch.setattr(
            otel_conformance_obi.urllib.request, "urlopen", refuse
        )

        with pytest.raises(LauncherError, match="no route"):
            install({"XDG_CACHE_HOME": str(tmp_path)})

    @staticmethod
    def serve_archive(
        monkeypatch: pytest.MonkeyPatch, digest: str | None = None
    ) -> str:
        payload = b"#!/bin/sh\n"
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as bundle:
            member = tarfile.TarInfo("obi")
            member.size = len(payload)
            bundle.addfile(member, io.BytesIO(payload))
        body = archive.getvalue()
        pinned = digest or hashlib.sha256(body).hexdigest()
        monkeypatch.setattr(
            otel_conformance_obi, "pin", lambda arch: ("v9.9.9", pinned)
        )
        monkeypatch.setattr(
            otel_conformance_obi.urllib.request,
            "urlopen",
            lambda url: io.BytesIO(body),
        )
        return pinned

    def test_an_archive_matching_its_pin_is_installed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self.serve_archive(monkeypatch)

        target = install({"XDG_CACHE_HOME": str(tmp_path)})

        assert target.read_bytes() == b"#!/bin/sh\n"
        assert (
            target == tmp_path / "otel-conformance" / "obi" / "v9.9.9" / "obi"
        )

    def test_an_archive_that_does_not_match_its_pin_is_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        self.serve_archive(monkeypatch, digest="0" * 64)

        with pytest.raises(LauncherError, match="SHA-256"):
            install({"XDG_CACHE_HOME": str(tmp_path)})

        assert not (
            tmp_path / "otel-conformance" / "obi" / "v9.9.9" / "obi"
        ).exists()


class TestThePins:
    PINS = textwrap.dedent(
        """\
        # renovate: datasource=github-release-attachments depName=x
        OBI_LINUX_AMD64=v2.0.0@sha256:{amd64}

        # renovate: datasource=github-release-attachments depName=x
        OBI_LINUX_ARM64=v2.0.0@sha256:{arm64}
        """
    ).format(amd64="a" * 64, arm64="b" * 64)

    def test_each_architecture_pins_a_release_and_a_digest(self) -> None:
        assert pins(self.PINS) == {
            "amd64": ("v2.0.0", "a" * 64),
            "arm64": ("v2.0.0", "b" * 64),
        }

    def test_a_file_without_pins_says_so(self) -> None:
        with pytest.raises(LauncherError, match="pins no OBI release"):
            pins("OBI_VERSION=v1.0.0\n")

    def test_the_shipped_pins_cover_every_architecture(self) -> None:
        shipped = pins()

        assert set(shipped) == set(otel_conformance_obi.ARCHITECTURES.values())
        assert len({release for release, _ in shipped.values()}) == 1

    def test_an_unpinned_architecture_says_so(self) -> None:
        with pytest.raises(LauncherError, match="no OBI build for riscv64"):
            pin("riscv64")


class TestTheConfig:
    def test_it_is_config_v2(self) -> None:
        config = rendered()

        assert config["file_format"] == "1.0"
        assert config["extensions"]["obi"]["version"] == "2.0"

    def test_it_selects_only_the_matching_processes(self) -> None:
        selector = {"exe_path_glob": ["/srv/java"], "cmd_args_glob": ["*Main"]}

        capture = rendered(selector)["extensions"]["obi"]["capture"]

        assert capture["policy"]["default_action"] == "exclude"
        assert capture["rules"][-1]["action"] == "include"
        assert capture["rules"][-1]["match"]["process"] == selector

    def test_the_launcher_and_its_ancestors_are_excluded_first(self) -> None:
        config = yaml.safe_load(
            render_config(
                config_template({}).read_text(),
                {"cmd_args_glob": ["*main.py"]},
                9400,
                {"OTEL_EXPORTER_OTLP_ENDPOINT": ENDPOINT},
                [4242, 17],
            )
        )
        capture = config["extensions"]["obi"]["capture"]

        assert capture["policy"]["match_order"] == "first_match_wins"
        assert capture["rules"][0] == {
            "action": "exclude",
            "name": "launcher",
            "match": {"process": {"target_pids": [4242, 17]}},
        }

    def test_it_exposes_the_instrumented_processes_metric(self) -> None:
        internal = rendered(port=9123)["extensions"]["obi"]["daemon"][
            "internal_metrics"
        ]

        assert internal == {
            "exporter": "prometheus",
            "prometheus": {"port": 9123, "path": "/metrics"},
        }

    def test_it_exports_to_the_runner(self) -> None:
        config = rendered()

        traces = config["tracer_provider"]["processors"][0]["batch"]
        metrics = config["meter_provider"]["readers"][0]["periodic"]
        assert traces["exporter"]["otlp_grpc"]["endpoint"] == ENDPOINT
        assert metrics["exporter"]["otlp_grpc"]["endpoint"] == ENDPOINT
        assert metrics["interval"] == METRIC_EXPORT_INTERVAL_MILLIS

    def test_both_exports_fit_in_the_settle_period(self) -> None:
        config = rendered()

        schedule = config["tracer_provider"]["processors"][0]["batch"][
            "schedule_delay"
        ]
        interval = config["meter_provider"]["readers"][0]["periodic"][
            "interval"
        ]
        settle = otel_conformance_obi.DEFAULT_SETTLE * 1000
        assert max(schedule, interval) < settle

    def test_every_attribute_is_selected(self) -> None:
        select = rendered()["extensions"]["obi"]["enrich"]["attributes"][
            "select"
        ]

        assert select == {"*": {"include": ["*"]}}

    def test_a_missing_endpoint_says_so(self) -> None:
        with pytest.raises(LauncherError, match="OTEL_EXPORTER_OTLP_ENDPOINT"):
            render_config("log_level: info\n", {}, 1, {})

    def test_only_grpc_is_exported(self) -> None:
        with pytest.raises(LauncherError, match="http/protobuf"):
            rendered(OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf")

    def test_an_unknown_reference_says_so(self) -> None:
        with pytest.raises(LauncherError, match="NOPE"):
            render_config(
                "x: ${NOPE}",
                {},
                1,
                {"OTEL_EXPORTER_OTLP_ENDPOINT": ENDPOINT},
            )

    def test_another_template_can_be_chosen(self, tmp_path: Path) -> None:
        other = tmp_path / "obi.yaml"

        assert config_template({CONFIG_VARIABLE: str(other)}) == other


class TestTheSelector:
    def test_by_default_it_is_the_resolved_command(self) -> None:
        assert process_match([sys.executable]) == {
            "exe_path_glob": [
                glob_literal(str(Path(sys.executable).resolve()))
            ]
        }

    def test_the_globs_replace_the_default(self) -> None:
        assert process_match(["uv", "run"], args="*main.py") == {
            "cmd_args_glob": ["*main.py"]
        }
        assert process_match(["uv"], exe="*/python3*", args="*main.py") == {
            "exe_path_glob": ["*/python3*"],
            "cmd_args_glob": ["*main.py"],
        }

    def test_a_command_that_is_not_found_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LauncherError, match="could not be started"):
            process_match([str(tmp_path / "missing")])

    def test_glob_characters_are_escaped_as_obi_reads_them(self) -> None:
        assert glob_literal("/a[b]/c*{d,e}?\\f") == r"/a\[b\]/c\*\{d,e\}\?\\f"

    @linux_only
    def test_the_default_selector_is_literal(self, tmp_path: Path) -> None:
        directory = tmp_path / "build[1]"
        directory.mkdir()
        scenario = directory / "scenario*"
        scenario.write_text("#!/bin/sh\n")
        scenario.chmod(0o755)

        selector = process_match([str(scenario)])

        assert selector == {
            "exe_path_glob": [glob_literal(str(scenario.resolve()))]
        }
        assert r"build\[1\]/scenario\*" in selector["exe_path_glob"][0]


class TestTheTimeouts:
    def test_an_unset_variable_takes_the_default(self) -> None:
        assert seconds({}, READY_TIMEOUT_VARIABLE, 45.0) == 45.0

    def test_a_number_of_seconds_is_read(self) -> None:
        assert (
            seconds(
                {READY_TIMEOUT_VARIABLE: "2.5"}, READY_TIMEOUT_VARIABLE, 45.0
            )
            == 2.5
        )

    @pytest.mark.parametrize("raw", ["3s", "-1", "nan", "inf", "-inf"])
    def test_anything_else_says_so(self, raw: str) -> None:
        with pytest.raises(LauncherError, match=READY_TIMEOUT_VARIABLE):
            seconds(
                {READY_TIMEOUT_VARIABLE: raw}, READY_TIMEOUT_VARIABLE, 45.0
            )

    def test_the_default_fits_inside_the_drive_startup_timeout(self) -> None:
        assert otel_conformance_obi.DEFAULT_READY_TIMEOUT < 60

    @linux_only
    def test_a_malformed_timeout_is_a_launcher_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fake = tmp_path / "obi"
        fake.write_text("#!/bin/sh\n")
        monkeypatch.setenv(BINARY_VARIABLE, str(fake))
        monkeypatch.setenv(SETTLE_VARIABLE, "3s")

        assert main(["run", "--args", "*", "true"]) == 1
        assert f"{SETTLE_VARIABLE} must be a number" in capsys.readouterr().err


class TestTheInstrumentedProcessesMetric:
    EXPOSITION = textwrap.dedent(
        """\
        # TYPE obi_instrumented_processes gauge
        obi_instrumented_processes{process_executable_name="java"} 0
        obi_instrumented_processes{process_executable_name="scenario"} 1
        obi_tracer_flushes_count 3
        """
    )

    def test_the_waiting_executable_counted_is_instrumented(self) -> None:
        assert instrumented(self.EXPOSITION, "scenario")

    def test_another_executable_counted_is_not(self) -> None:
        assert not instrumented(self.EXPOSITION, "python3")

    def test_a_zero_count_is_not(self) -> None:
        assert not instrumented(self.EXPOSITION, "java")

    def test_no_series_is_not(self) -> None:
        assert not instrumented("obi_tracer_flushes_count 3\n", "scenario")
        assert not instrumented("", "scenario")


@linux_only
class TestTheLauncherLineage:
    def test_it_starts_at_the_launcher_and_walks_up(self) -> None:
        found = lineage()

        assert found[0] == os.getpid()
        assert os.getppid() in found or os.getppid() <= 1
        assert 1 not in found


class TestTheExitStatus:
    @pytest.mark.parametrize(("code", "status"), [(0, 0), (3, 3), (-15, 143)])
    def test_a_signal_maps_to_its_shell_status(
        self, code: int, status: int
    ) -> None:
        assert exit_status(code) == status


@linux_only
class TestRunningUnderOBI:
    @pytest.fixture
    def environ(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> dict[str, str]:
        fake = tmp_path / "fake-obi"
        fake.write_text(f"#!{sys.executable}\n{FAKE_OBI}")
        fake.chmod(0o755)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            otel_conformance_obi, "_privileged", lambda command: command
        )
        return {
            BINARY_VARIABLE: str(fake),
            "OTEL_EXPORTER_OTLP_ENDPOINT": ENDPOINT,
            SETTLE_VARIABLE: "0.2",
            READY_TIMEOUT_VARIABLE: "20",
        }

    def test_the_scenario_status_is_returned(
        self, environ: dict[str, str]
    ) -> None:
        assert run(gated(3), args=SELECT_GATED, environ=environ) == 3

    def test_obi_logs_only_to_standard_error(
        self, environ: dict[str, str], capfd: pytest.CaptureFixture[str]
    ) -> None:
        run(gated(), args=SELECT_GATED, environ=environ)

        out, err = capfd.readouterr()
        assert "fake obi on stdout" in err
        assert "fake obi on stderr" in err
        assert "fake obi" not in out

    def test_the_scenario_is_released_only_once_obi_attached_it(
        self, environ: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FAKE_OBI_MODE", "slow")

        assert run(gated(), args=SELECT_GATED, environ=environ) == 0

    def test_a_wrapped_scenario_is_selected_by_its_command_line(
        self, environ: dict[str, str]
    ) -> None:
        command = ["/bin/sh", "-c", shell(gated()) + "; exit $?"]

        assert run(command, args=SELECT_GATED, environ=environ) == 0

    def test_a_selector_that_misses_the_scenario_fails(
        self, environ: dict[str, str]
    ) -> None:
        environ[READY_TIMEOUT_VARIABLE] = "1"

        with pytest.raises(LauncherError, match="did not instrument"):
            run(gated(), args="* another-scenario", environ=environ)

    def test_obi_exiting_before_it_is_ready_fails(
        self, environ: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FAKE_OBI_MODE", "die-early")

        with pytest.raises(LauncherError, match="before instrumenting"):
            run(gated(), args=SELECT_GATED, environ=environ)

    def test_a_failed_launch_kills_a_wrapped_scenario_before_its_workload(
        self,
        environ: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("FAKE_OBI_MODE", "die-early")
        command = ["/bin/sh", "-c", shell(gated()) + "; exit $?"]

        with pytest.raises(LauncherError, match="before instrumenting"):
            run(command, args=SELECT_GATED, environ=environ)

        pid = int((tmp_path / "scenario.pid").read_text())
        assert not running(pid)
        assert not (tmp_path / "released").exists()

    def test_obi_exiting_while_the_scenario_runs_fails(
        self, environ: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FAKE_OBI_MODE", "die-later")

        with pytest.raises(
            LauncherError,
            match="while the scenario ran .the scenario exited with status 3",
        ):
            run(gated(3), args=SELECT_GATED, environ=environ)

    def test_the_gate_and_the_attach_share_one_deadline(
        self, environ: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FAKE_OBI_MODE", "slow")
        environ[READY_TIMEOUT_VARIABLE] = "1.2"
        command = ["/bin/sh", "-c", "sleep 0.8; exec " + shell(gated())]

        with pytest.raises(LauncherError, match="within 1.2s"):
            run(command, args=SELECT_GATED, environ=environ)

    def test_the_signal_handlers_are_restored(
        self, environ: dict[str, str]
    ) -> None:
        before = {
            signum: signal.getsignal(signum)
            for signum in (signal.SIGINT, signal.SIGTERM)
        }

        run(gated(), args=SELECT_GATED, environ=environ)

        assert {
            signum: signal.getsignal(signum) for signum in before
        } == before

    def test_an_interrupt_after_the_scenario_exits_is_not_swallowed(
        self, environ: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GATED_INTERRUPT_LAUNCHER", "1")
        environ[SETTLE_VARIABLE] = "10"
        started = time.monotonic()

        with pytest.raises(KeyboardInterrupt):
            run(gated(), args=SELECT_GATED, environ=environ)

        assert time.monotonic() - started < 8

    def test_obi_and_the_scenario_stop_when_the_launcher_is_killed(
        self, environ: dict[str, str], tmp_path: Path
    ) -> None:
        launched = launcher(
            tmp_path,
            {**environ, "GATED_LINGER": "30"},
            "--args",
            SELECT_GATED,
            *gated(),
        )
        try:
            wait_for(tmp_path / "obi.pid", tmp_path / "released")
            obi_pid = int((tmp_path / "obi.pid").read_text())
            scenario_pid = int((tmp_path / "scenario.pid").read_text())

            os.kill(launched.pid, signal.SIGKILL)
            launched.wait()

            assert not running(obi_pid)
            assert not running(scenario_pid)
        finally:
            cleanup(tmp_path, launched)

    def test_a_scenario_still_starting_when_the_launcher_dies_is_killed(
        self, environ: dict[str, str], tmp_path: Path
    ) -> None:
        launched = launcher(
            tmp_path,
            {**environ, "GATED_DELAY": "1"},
            "--args",
            SELECT_GATED,
            *gated(),
        )
        try:
            wait_for(tmp_path / "scenario.pid")
            scenario_pid = int((tmp_path / "scenario.pid").read_text())

            os.kill(launched.pid, signal.SIGKILL)
            launched.wait()

            assert not running(scenario_pid)
            assert not (tmp_path / "released").exists()
        finally:
            cleanup(tmp_path, launched)

    def test_an_args_selector_matching_the_launcher_waits_for_the_scenario(
        self, environ: dict[str, str], tmp_path: Path
    ) -> None:
        launched = launcher(
            tmp_path, environ, "--args", SELECT_GATED, *gated()
        )
        try:
            assert launched.wait(60) == 0
            attached = int((tmp_path / "attached").read_text())
            assert attached == int((tmp_path / "scenario.pid").read_text())
        finally:
            cleanup(tmp_path, launched)

    def test_the_watchdog_does_not_hold_the_launcher_output_open(
        self, environ: dict[str, str], tmp_path: Path
    ) -> None:
        started = time.monotonic()
        launched = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, otel_conformance_obi as obi; "
                "obi._privileged = lambda command: command; "
                "sys.exit(obi.main(sys.argv[1:]))",
                "run",
                "--args",
                SELECT_GATED,
                *gated(),
            ],
            cwd=tmp_path,
            env={**os.environ, **environ},
            capture_output=True,
            timeout=60,
            check=False,
        )

        assert launched.returncode == 0, launched.stderr
        assert time.monotonic() - started < 15

    def test_a_finished_scenario_is_not_killed_after_the_fact(
        self, environ: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FAKE_OBI_MODE", "die-later")
        signalled: list[tuple[int, int]] = []
        killpg = os.killpg

        def record(pgid: int, signum: int) -> None:
            signalled.append((pgid, signum))
            killpg(pgid, signum)

        monkeypatch.setattr(otel_conformance_obi.os, "killpg", record)

        with pytest.raises(LauncherError, match="while the scenario ran"):
            run(gated(), args=SELECT_GATED, environ=environ)

        assert signalled == []

    def test_the_reaper_stands_down_as_soon_as_the_scenario_exits(
        self, environ: dict[str, str], tmp_path: Path
    ) -> None:
        launched = launcher(
            tmp_path,
            {**environ, SETTLE_VARIABLE: "20"},
            "--args",
            SELECT_GATED,
            *gated(),
        )
        try:
            wait_for(tmp_path / "released")
            scenario_pid = int((tmp_path / "scenario.pid").read_text())
            assert not running(scenario_pid)
            time.sleep(0.5)

            assert running_scripts(otel_conformance_obi.REAPER) == []
            assert launched.poll() is None
        finally:
            cleanup(tmp_path, launched)

    def test_a_reaper_that_cannot_start_takes_the_scenario_with_it(
        self,
        environ: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        command = gated()
        monkeypatch.setattr(
            otel_conformance_obi.sys, "executable", str(tmp_path / "missing")
        )

        with pytest.raises(LauncherError, match="reaper could not be started"):
            run(command, args=SELECT_GATED, environ=environ)

        time.sleep(0.5)
        assert gated_children() == []

    def test_the_reaper_never_satisfies_readiness(
        self, environ: dict[str, str]
    ) -> None:
        interpreter = glob_literal(os.path.realpath(sys.executable))

        assert run(gated(), exe=interpreter, environ=environ) == 0

    def test_a_wrapper_that_exits_takes_its_gated_child_with_it(
        self,
        environ: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("GATED_DELAY", "1")
        command = ["/bin/sh", "-c", shell(gated()) + " & exit 0"]

        with pytest.raises(LauncherError, match="before reaching the gate"):
            run(command, args=SELECT_GATED, environ=environ)

        time.sleep(1.5)
        assert gated_children() == []
        assert not (tmp_path / "released").exists()

    def test_a_scenario_held_by_a_killed_launcher_never_runs(
        self, environ: dict[str, str], tmp_path: Path
    ) -> None:
        launched = launcher(
            tmp_path, environ, "--args", "* another-scenario", *gated()
        )
        wait_for(tmp_path / "obi.pid", tmp_path / "scenario.pid")
        scenario_pid = int((tmp_path / "scenario.pid").read_text())

        os.kill(launched.pid, signal.SIGKILL)
        launched.wait()

        assert not running(scenario_pid)
        assert not (tmp_path / "released").exists()

    def test_a_scenario_that_exits_before_the_gate_fails(
        self, environ: dict[str, str]
    ) -> None:
        with pytest.raises(LauncherError, match="status 5 before reaching"):
            run([sys.executable, "-c", "raise SystemExit(5)"], environ=environ)

    def test_a_scenario_that_never_reaches_the_gate_fails(
        self, environ: dict[str, str]
    ) -> None:
        environ[READY_TIMEOUT_VARIABLE] = "0.5"

        with pytest.raises(LauncherError, match="did not reach the gate"):
            run(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                environ=environ,
            )

    def test_a_command_that_cannot_start_says_so(
        self,
        environ: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        for name, value in environ.items():
            monkeypatch.setenv(name, value)

        assert main(["run", str(tmp_path / "missing")]) == 1
        assert "could not be started" in capsys.readouterr().err
