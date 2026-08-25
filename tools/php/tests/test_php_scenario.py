# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import threading
from pathlib import Path

import pytest

import otel_conformance_php
from otel_conformance_php import (
    BUILD_MARKER,
    PORT_VARIABLE,
    LayoutError,
    composer_command,
    package_root,
    php_command,
    serve,
)


@pytest.fixture
def package(tmp_path: Path) -> Path:
    (tmp_path / BUILD_MARKER).write_text("{}", encoding="utf-8")
    return tmp_path


def test_package_is_found_above_the_scenario(package: Path) -> None:
    scenario = package / "server"
    scenario.mkdir()

    assert package_root(scenario) == package


def test_missing_package_is_reported(tmp_path: Path) -> None:
    with pytest.raises(LayoutError, match=BUILD_MARKER):
        package_root(tmp_path)


def test_composer_is_resolved_portably(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        otel_conformance_php.shutil,
        "which",
        lambda command: f"C:/tools/{command}.bat",
    )

    assert composer_command()[0] == "C:/tools/composer.bat"


def test_install_runs_from_the_package(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], Path]] = []
    scenario = package / "server"
    scenario.mkdir()
    monkeypatch.chdir(scenario)
    monkeypatch.setattr(
        otel_conformance_php.subprocess,
        "call",
        lambda command, cwd: calls.append((command, cwd)) or 0,
    )

    assert otel_conformance_php.main(["install"]) == 0
    assert calls[0][1] == package
    assert calls[0][0][1] == "install"


def test_install_reports_missing_composer(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def composer_missing(command: list[str], cwd: Path) -> int:
        raise FileNotFoundError(command[0])

    monkeypatch.chdir(package)
    monkeypatch.setattr(
        otel_conformance_php.subprocess,
        "call",
        composer_missing,
    )

    assert otel_conformance_php.main(["install"]) == 1
    assert capsys.readouterr().err == (
        "installing PHP scenario dependencies requires composer on PATH\n"
    )


def test_php_server_binds_loopback(package: Path) -> None:
    router = package / "router.php"

    assert php_command("4317", router)[1:] == [
        "-S",
        "127.0.0.1:4317",
        str(router),
    ]


def test_serve_reports_missing_php(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.setenv("OTEL_HTTP_SCENARIO_PORT", "8080")

    def php_missing(command: list[str], *, stdin: int) -> None:
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(
        otel_conformance_php.subprocess,
        "Popen",
        php_missing,
    )

    assert otel_conformance_php.main(["serve", str(router)]) == 1
    assert capsys.readouterr().err == (
        "serving a PHP scenario requires php to be available on PATH\n"
    )


@pytest.mark.parametrize("port", ["-1", "0", "65536", "not-a-port"])
def test_serve_reports_invalid_port(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    port: str,
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.setenv(PORT_VARIABLE, port)

    assert otel_conformance_php.main(["serve", str(router)]) == 1
    assert capsys.readouterr().err == (
        f"{PORT_VARIABLE} must be an integer from 1 to 65535: {port}\n"
    )


def test_serve_stops_the_server_at_eof(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.setenv("OTEL_HTTP_SCENARIO_PORT", "8080")

    class Process:
        returncode: int | None = None
        terminated = False

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout: int | None = None) -> int:
            assert timeout == otel_conformance_php._SHUTDOWN_TIMEOUT_SECONDS
            return self.returncode or 0

    process = Process()
    monkeypatch.setattr(
        otel_conformance_php.subprocess,
        "Popen",
        lambda command, stdin: process,
    )

    assert serve(router, input_stream=io.BytesIO()) == 0
    assert process.terminated


def test_serve_reports_server_that_exits_cleanly_before_eof(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.setenv("OTEL_HTTP_SCENARIO_PORT", "8080")
    release = threading.Event()

    class Input:
        def read(self, size: int = -1) -> bytes:
            release.wait()
            return b""

    class Process:
        returncode = 0

        def poll(self) -> int:
            return self.returncode

    monkeypatch.setattr(
        otel_conformance_php.subprocess,
        "Popen",
        lambda command, stdin: Process(),
    )

    try:
        assert serve(router, input_stream=Input()) == 1  # type: ignore[arg-type]
    finally:
        release.set()


def test_missing_router_fails_tightly(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_HTTP_SCENARIO_PORT", "8080")

    with pytest.raises(LayoutError, match="router does not exist"):
        serve(package / "missing.php", input_stream=io.BytesIO())
