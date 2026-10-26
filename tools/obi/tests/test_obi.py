# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import subprocess
import sys
import textwrap
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
    install,
    instrumented,
    main,
    process_match,
    render_config,
    run,
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
    selector = obi["capture"]["rules"][0]["match"]["process"]
    mode = os.environ.get("FAKE_OBI_MODE", "ready")
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
        for entry in os.listdir("/proc"):
            if entry.isdigit() and int(entry) not in (os.getpid(), os.getppid()) and matches(entry):
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
    import os, pathlib, sys
    with open(os.environ["OTEL_CONFORMANCE_GATE"], "rb") as gate:
        gate.read()
    attached = pathlib.Path("attached")
    instrumented = attached.exists() and attached.read_text() == str(os.getpid())
    sys.exit(int(sys.argv[1]) if instrumented else 99)
    """
)


def gated(status: int = 0) -> list[str]:
    return [sys.executable, "-c", GATED, str(status), MARKER]


def shell(command: list[str]) -> str:
    return " ".join(f"'{part}'" for part in command)


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


class TestTheConfig:
    def test_it_is_config_v2(self) -> None:
        config = rendered()

        assert config["file_format"] == "1.0"
        assert config["extensions"]["obi"]["version"] == "2.0"

    def test_it_selects_only_the_matching_processes(self) -> None:
        selector = {"exe_path_glob": ["/srv/java"], "cmd_args_glob": ["*Main"]}

        capture = rendered(selector)["extensions"]["obi"]["capture"]

        assert capture["policy"]["default_action"] == "exclude"
        assert [rule["match"]["process"] for rule in capture["rules"]] == [
            selector
        ]

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
            "exe_path_glob": [str(Path(sys.executable).resolve())]
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


class TestTheInstrumentedProcessesMetric:
    EXPOSITION = textwrap.dedent(
        """\
        # TYPE obi_instrumented_processes gauge
        obi_instrumented_processes{process_executable_name="java"} 0
        obi_instrumented_processes{process_executable_name="scenario"} 1
        obi_tracer_flushes_count 3
        """
    )

    def test_a_counted_process_is_instrumented(self) -> None:
        assert instrumented(self.EXPOSITION)

    def test_only_zero_counts_are_not(self) -> None:
        assert not instrumented(
            'obi_instrumented_processes{process_executable_name="java"} 0\n'
        )

    def test_no_series_is_not(self) -> None:
        assert not instrumented("obi_tracer_flushes_count 3\n")
        assert not instrumented("")


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
            otel_conformance_obi,
            "obi_command",
            lambda executable, config: [
                str(executable),
                "-config",
                str(config),
            ],
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

    def test_obi_exiting_while_the_scenario_runs_fails(
        self, environ: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FAKE_OBI_MODE", "die-later")

        with pytest.raises(LauncherError, match="while the scenario ran"):
            run(gated(), args=SELECT_GATED, environ=environ)

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
