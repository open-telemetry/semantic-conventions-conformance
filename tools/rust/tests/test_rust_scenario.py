# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Rust toolchain that a scenario directory no longer has to restate."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import otel_conformance_rust
from otel_conformance_rust import (
    MANIFEST,
    CargoPackage,
    LayoutError,
    binary,
    build_command,
    cargo_package,
    package_manifest,
    run_command,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / MANIFEST).write_text(
        '[workspace]\nmembers = ["server"]\n',
        encoding="utf-8",
    )
    package = tmp_path / "server"
    package.mkdir()
    (package / MANIFEST).write_text(
        '[package]\nname = "rust-server"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def package(root: Path) -> CargoPackage:
    return CargoPackage(
        manifest=(root / "server" / MANIFEST).resolve(),
        target_directory=root / "custom-target",
        binary_name="rust-server",
    )


def metadata(
    package: CargoPackage,
    *,
    binaries: tuple[str, ...] | None = None,
    default_run: str | None = None,
) -> dict[str, object]:
    names = binaries or (package.binary_name,)
    return {
        "workspace_root": str(package.manifest.parent.parent),
        "target_directory": str(package.target_directory),
        "packages": [
            {
                "manifest_path": str(package.manifest),
                "default_run": default_run,
                "targets": [
                    {"name": name, "kind": ["bin"]} for name in names
                ],
            }
        ],
    }


class TestFindingThePackage:
    def test_the_package_is_the_nearest_manifest(self, root: Path) -> None:
        scenario = root / "server" / "scenario"
        scenario.mkdir()

        assert package_manifest(scenario) == root / "server" / MANIFEST

    def test_being_outside_a_package_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LayoutError, match="package"):
            package_manifest(tmp_path)


class TestBuilding:
    def test_it_builds_the_current_package_in_release_mode(
        self, package: CargoPackage
    ) -> None:
        command = build_command(package)

        assert "--release" in command
        assert "--locked" in command
        assert command[command.index("--manifest-path") + 1] == str(
            package.manifest
        )
        assert command[command.index("--bin") + 1] == package.binary_name


class TestCommandLineErrors:
    def test_run_help_is_handled_by_the_launcher(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exit_info:
            otel_conformance_rust.main(["run", "--help"])

        assert exit_info.value.code == 0
        assert "usage: otel-conformance-rust run" in capsys.readouterr().out

    def test_only_run_accepts_unknown_arguments(self) -> None:
        with pytest.raises(SystemExit) as exit_info:
            otel_conformance_rust.main(["build", "--flag"])

        assert exit_info.value.code == 2

    def test_missing_package_is_reported(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.chdir(tmp_path)

        assert otel_conformance_rust.main(["build"]) == 1
        assert "error: no package Cargo.toml" in capsys.readouterr().err

    def test_missing_executable_is_reported(
        self,
        package: CargoPackage,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def missing(command: list[str]) -> int:
            raise FileNotFoundError(2, "No such file or directory")

        monkeypatch.chdir(package.manifest.parent)
        monkeypatch.setattr(
            otel_conformance_rust, "cargo_package", lambda _: package
        )
        monkeypatch.setattr(otel_conformance_rust.subprocess, "call", missing)

        assert otel_conformance_rust.main(["build"]) == 1
        assert (
            "otel-conformance-rust: error: cargo was not found"
            in capsys.readouterr().err
        )

    def test_missing_cargo_is_reported_before_running(
        self,
        package: CargoPackage,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def missing(
            command: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError(2, "No such file or directory")

        monkeypatch.chdir(package.manifest.parent)
        monkeypatch.setattr(otel_conformance_rust.subprocess, "run", missing)

        assert otel_conformance_rust.main(["run"]) == 1
        assert (
            "otel-conformance-rust: error: cargo was not found"
            in capsys.readouterr().err
        )

    def test_missing_scenario_binary_suggests_building(
        self,
        package: CargoPackage,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def missing(command: list[str]) -> int:
            raise FileNotFoundError(2, "No such file or directory")

        monkeypatch.chdir(package.manifest.parent)
        monkeypatch.setattr(
            otel_conformance_rust, "cargo_package", lambda _: package
        )
        monkeypatch.setattr(otel_conformance_rust.subprocess, "call", missing)

        assert otel_conformance_rust.main(["run"]) == 1
        assert (
            "scenario binary was not found; run "
            "`otel-conformance-rust build` first"
            in capsys.readouterr().err
        )


class TestRunning:
    def test_the_binary_is_absolute_and_platform_specific(
        self, package: CargoPackage
    ) -> None:
        path = binary(package)

        assert path.is_absolute()
        assert path.name == f"rust-server{'.exe' if os.name == 'nt' else ''}"

    def test_the_layout_comes_from_cargo(
        self, package: CargoPackage, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands: list[list[str]] = []

        def cargo_metadata(
            command: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(metadata(package)),
            )

        monkeypatch.setattr(
            otel_conformance_rust.subprocess, "run", cargo_metadata
        )

        assert cargo_package(package.manifest) == package
        assert commands[0][0:2] == ["cargo", "metadata"]
        assert commands[0][commands[0].index("--manifest-path") + 1] == str(
            package.manifest
        )

    def test_the_binary_target_name_comes_from_cargo(
        self, package: CargoPackage, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        expected = CargoPackage(
            package.manifest,
            package.target_directory,
            "scenario-server",
        )
        monkeypatch.setattr(
            otel_conformance_rust.subprocess,
            "run",
            lambda command, **_: subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(metadata(expected)),
            ),
        )

        assert cargo_package(package.manifest) == expected

    def test_default_run_selects_one_of_multiple_binaries(
        self, package: CargoPackage, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            otel_conformance_rust.subprocess,
            "run",
            lambda command, **_: subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    metadata(
                        package,
                        binaries=("first", "scenario-server"),
                        default_run="scenario-server",
                    )
                ),
            ),
        )

        assert cargo_package(package.manifest).binary_name == "scenario-server"

    def test_multiple_binaries_without_default_run_are_rejected(
        self, package: CargoPackage, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            otel_conformance_rust.subprocess,
            "run",
            lambda command, **_: subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    metadata(package, binaries=("first", "second"))
                ),
            ),
        )

        with pytest.raises(LayoutError, match="multiple binary targets"):
            cargo_package(package.manifest)

    def test_cargo_metadata_failure_is_a_layout_error(
        self, package: CargoPackage, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def cargo_metadata(
            command: list[str], **options: object
        ) -> subprocess.CompletedProcess[str]:
            assert options["check"] is False
            return subprocess.CompletedProcess(
                command,
                101,
                stdout="",
                stderr="invalid Cargo.lock",
            )

        monkeypatch.setattr(
            otel_conformance_rust.subprocess, "run", cargo_metadata
        )

        with pytest.raises(LayoutError, match="invalid Cargo.lock"):
            cargo_package(package.manifest)

    def test_non_json_cargo_metadata_is_a_layout_error(
        self, package: CargoPackage, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def cargo_metadata(
            command: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="not JSON",
                stderr="",
            )

        monkeypatch.setattr(
            otel_conformance_rust.subprocess, "run", cargo_metadata
        )

        with pytest.raises(LayoutError, match="not JSON"):
            cargo_package(package.manifest)

    def test_arguments_reach_the_scenario(
        self, package: CargoPackage, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands: list[list[str]] = []
        monkeypatch.chdir(package.manifest.parent)
        monkeypatch.setattr(
            otel_conformance_rust, "cargo_package", lambda _: package
        )
        monkeypatch.setattr(
            otel_conformance_rust.subprocess,
            "call",
            lambda command: commands.append(command) or 0,
        )

        assert otel_conformance_rust.main(["run", "--flag", "value"]) == 0
        assert commands[0][1:] == ["--flag", "value"]

    def test_running_executes_what_building_produced(
        self, package: CargoPackage
    ) -> None:
        assert run_command(package)[0] == str(binary(package))
