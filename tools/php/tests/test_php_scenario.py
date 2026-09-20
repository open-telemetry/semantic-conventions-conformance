# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import io
import json
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

import pytest

import otel_conformance_php
from otel_conformance_php import (
    BUILD_MARKER,
    PORT_VARIABLE,
    LayoutError,
    check_lock,
    composer_command,
    lock_problems,
    package_root,
    path_packages,
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


def test_serve_reports_missing_port(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.delenv(PORT_VARIABLE, raising=False)

    assert otel_conformance_php.main(["serve", str(router)]) == 1
    assert capsys.readouterr().err == (
        f"required environment variable is missing: {PORT_VARIABLE}\n"
    )


def test_serve_reports_missing_php(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.setenv(PORT_VARIABLE, "8080")

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
    monkeypatch.setenv(PORT_VARIABLE, "8080")

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


def test_serve_tolerates_server_exit_during_terminate(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.setenv(PORT_VARIABLE, "8080")

    class Process:
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 0
            raise OSError("process already exited")

        def wait(self, timeout: int | None = None) -> int:
            assert timeout == otel_conformance_php._SHUTDOWN_TIMEOUT_SECONDS
            return self.returncode or 0

    monkeypatch.setattr(
        otel_conformance_php.subprocess,
        "Popen",
        lambda command, stdin: Process(),
    )

    assert serve(router, input_stream=io.BytesIO()) == 0


def test_serve_tolerates_server_exit_during_kill(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.setenv(PORT_VARIABLE, "8080")

    class Process:
        returncode: int | None = None
        waits = 0

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            pass

        def kill(self) -> None:
            self.returncode = 0
            raise OSError("process already exited")

        def wait(self, timeout: int | None = None) -> int:
            self.waits += 1
            if self.waits == 1:
                raise subprocess.TimeoutExpired("php", timeout)
            assert timeout is None
            return self.returncode or 0

    monkeypatch.setattr(
        otel_conformance_php.subprocess,
        "Popen",
        lambda command, stdin: Process(),
    )

    assert serve(router, input_stream=io.BytesIO()) == 1


def test_serve_reports_server_that_exits_cleanly_before_eof(
    package: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = package / "router.php"
    router.write_text("<?php", encoding="utf-8")
    monkeypatch.setenv(PORT_VARIABLE, "8080")
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
    monkeypatch.setenv(PORT_VARIABLE, "8080")

    with pytest.raises(LayoutError, match="router does not exist"):
        serve(package / "missing.php", input_stream=io.BytesIO())


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def locked(name: str, version: str, **fields: object) -> dict[str, object]:
    return {"name": name, "version": version, **fields}


def path_entry(**fields: object) -> dict[str, object]:
    return locked(
        "acme/client",
        "dev-main",
        type="library",
        dist={"type": "path", "url": "../client"},
        **fields,
    )


@pytest.fixture
def scenario(tmp_path: Path) -> Path:
    """A scenario whose lock is consistent with its path package."""
    root = tmp_path / "scenario"
    write_json(
        root / "composer.lock",
        {
            "packages": [
                locked("acme/yaml", "v8.1.6"),
                path_entry(
                    require={"php": ">=8.2", "acme/yaml": "^8.0"},
                    autoload={"psr-4": {"Acme\\": "src/"}},
                ),
            ]
        },
    )
    write_json(
        tmp_path / "client" / "composer.json",
        {
            "name": "acme/client",
            "require": {"php": ">=8.2", "acme/yaml": "^8.0"},
            "autoload": {"psr-4": {"Acme\\": "src/"}},
        },
    )
    write_json(
        tmp_path / "client" / "composer.lock",
        {"packages": [locked("acme/yaml", "v8.1.6")]},
    )
    return root


def edit_json(path: Path, edit: Callable[[dict[str, Any]], None]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    write_json(path, data)


def test_path_packages_are_found_in_the_lock(scenario: Path) -> None:
    assert path_packages(scenario / "composer.lock") == ["acme/client"]


def test_consistent_lock_has_no_problems(scenario: Path) -> None:
    assert lock_problems(scenario) == []
    check_lock(scenario)


def test_lock_without_path_packages_or_lockfile_is_skipped(
    tmp_path: Path,
) -> None:
    assert lock_problems(tmp_path) == []
    write_json(tmp_path / "composer.lock", {"packages": [locked("a/b", "1")]})
    assert lock_problems(tmp_path) == []


def test_stale_requirement_is_reported(scenario: Path) -> None:
    edit_json(
        scenario / "composer.lock",
        lambda lock: lock["packages"][1]["require"].update(
            {"acme/yaml": "^7.2"}
        ),
    )

    [problem] = lock_problems(scenario)

    assert "acme/client: the lock has require" in problem
    assert "^7.2" in problem
    assert "../client/composer.json has" in problem
    assert "^8.0" in problem


def test_stale_autoload_is_reported(scenario: Path) -> None:
    edit_json(
        scenario.parent / "client" / "composer.json",
        lambda manifest: manifest.update(
            {"autoload": {"psr-4": {"Acme\\": "lib/"}}}
        ),
    )

    [problem] = lock_problems(scenario)

    assert "the lock has autoload" in problem


def test_missing_type_means_library(scenario: Path) -> None:
    # The lock records Composer's default type; the source need not.
    edit_json(
        scenario.parent / "client" / "composer.json",
        lambda manifest: manifest.pop("type", None),
    )

    assert lock_problems(scenario) == []


def test_changed_type_is_reported(scenario: Path) -> None:
    edit_json(
        scenario.parent / "client" / "composer.json",
        lambda manifest: manifest.update({"type": "project"}),
    )

    [problem] = lock_problems(scenario)

    assert "the lock has type" in problem


def test_version_that_differs_from_the_package_lock_is_reported(
    scenario: Path,
) -> None:
    edit_json(
        scenario / "composer.lock",
        lambda lock: lock["packages"][0].update({"version": "v7.4.18"}),
    )

    [problem] = lock_problems(scenario)

    assert problem == (
        "acme/client: acme/yaml is locked at v7.4.18 but the package's own "
        "composer.lock pins v8.1.6"
    )


def test_requirement_missing_from_the_scenario_lock_is_reported(
    scenario: Path,
) -> None:
    edit_json(
        scenario / "composer.lock",
        lambda lock: lock["packages"].pop(0),
    )

    [problem] = lock_problems(scenario)

    assert "acme/yaml is locked at nothing" in problem


def test_platform_requirements_are_not_compared(scenario: Path) -> None:
    edit_json(
        scenario.parent / "client" / "composer.lock",
        lambda lock: lock["packages"].append(locked("php", "8.4.1")),
    )

    assert lock_problems(scenario) == []


def test_path_package_without_a_lock_skips_the_version_check(
    scenario: Path,
) -> None:
    (scenario.parent / "client" / "composer.lock").unlink()
    edit_json(
        scenario / "composer.lock",
        lambda lock: lock["packages"][0].update({"version": "v7.4.18"}),
    )

    assert lock_problems(scenario) == []


def test_missing_path_package_is_reported(scenario: Path) -> None:
    (scenario.parent / "client" / "composer.json").unlink()

    assert lock_problems(scenario) == [
        "acme/client: there is no composer.json at ../client"
    ]


def test_every_problem_is_reported_together(scenario: Path) -> None:
    def stale(lock: dict[str, Any]) -> None:
        lock["packages"][0]["version"] = "v7.4.18"
        lock["packages"][1]["require"]["acme/yaml"] = "^7.2"

    edit_json(scenario / "composer.lock", stale)

    with pytest.raises(LayoutError) as error:
        check_lock(scenario)

    message = str(error.value)
    assert message.count("\n  - ") == 2
    assert "composer update acme/client --with-dependencies" in message


def test_path_is_resolved_from_the_lock_not_the_working_directory(
    scenario: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert lock_problems(scenario) == []


def test_invalid_lock_is_reported(tmp_path: Path) -> None:
    (tmp_path / "composer.lock").write_text("{", encoding="utf-8")

    with pytest.raises(LayoutError, match="is not valid JSON"):
        lock_problems(tmp_path)


def test_install_fails_before_composer_when_the_lock_is_stale(
    scenario: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (scenario / BUILD_MARKER).write_text("{}", encoding="utf-8")
    edit_json(
        scenario / "composer.lock",
        lambda lock: lock["packages"][1]["require"].update(
            {"acme/yaml": "^7.2"}
        ),
    )

    def composer(command: list[str], cwd: Path) -> int:
        raise AssertionError(command)

    monkeypatch.chdir(scenario)
    monkeypatch.setattr(otel_conformance_php.subprocess, "call", composer)

    assert otel_conformance_php.main(["install"]) == 1
    assert "is out of date with its path packages" in capsys.readouterr().err


def test_check_lock_does_not_run_composer(
    scenario: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (scenario / BUILD_MARKER).write_text("{}", encoding="utf-8")

    def composer(command: list[str], cwd: Path) -> int:
        raise AssertionError(command)

    monkeypatch.chdir(scenario)
    monkeypatch.setattr(otel_conformance_php.subprocess, "call", composer)

    assert otel_conformance_php.main(["check-lock"]) == 0
