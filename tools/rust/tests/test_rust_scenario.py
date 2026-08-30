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
    LayoutError,
    binary,
    build_command,
    package_manifest,
    run_command,
    target_directory,
    workspace_root,
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


class TestFindingTheWorkspace:
    def test_it_is_found_from_a_scenario_directory(self, root: Path) -> None:
        scenario = root / "server" / "scenario"
        scenario.mkdir()

        assert workspace_root(scenario) == root

    def test_it_honors_a_package_workspace_path(
        self, tmp_path: Path
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / MANIFEST).write_text(
            "[workspace]\nmembers = []\n",
            encoding="utf-8",
        )
        package = tmp_path / "tools" / "scenario"
        package.mkdir(parents=True)
        (package / MANIFEST).write_text(
            '[package]\nname = "scenario"\nworkspace = "../../workspace"\n',
            encoding="utf-8",
        )

        assert workspace_root(package) == workspace

    def test_the_package_is_the_nearest_manifest(self, root: Path) -> None:
        scenario = root / "server" / "scenario"
        scenario.mkdir()

        assert package_manifest(scenario) == root / "server" / MANIFEST

    def test_literal_package_name_is_supported(self, root: Path) -> None:
        manifest = root / "server" / MANIFEST
        manifest.write_text(
            "[package]\nname = 'rust-server'\nversion = '0.1.0'\n",
            encoding="utf-8",
        )

        assert package_manifest(root / "server") == manifest

    def test_being_outside_a_workspace_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LayoutError, match="workspace"):
            workspace_root(tmp_path)


class TestBuilding:
    def test_it_builds_the_current_package_in_release_mode(
        self, root: Path
    ) -> None:
        manifest = root / "server" / MANIFEST
        command = build_command(manifest)

        assert "--release" in command
        assert "--locked" in command
        assert command[command.index("--manifest-path") + 1] == str(manifest)


class TestCommandLineErrors:
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
        root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def missing(command: list[str]) -> int:
            raise FileNotFoundError(2, "No such file or directory", command[0])

        monkeypatch.chdir(root / "server")
        monkeypatch.setattr(otel_conformance_rust.subprocess, "call", missing)

        assert otel_conformance_rust.main(["build"]) == 1
        assert (
            "otel-conformance-rust: error: cargo was not found"
            in capsys.readouterr().err
        )

    def test_missing_scenario_binary_suggests_building(
        self,
        root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def missing(command: list[str]) -> int:
            raise FileNotFoundError(2, "No such file or directory", command[0])

        monkeypatch.chdir(root / "server")
        monkeypatch.setattr(
            otel_conformance_rust,
            "target_directory",
            lambda _: root / "custom-target",
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
        self, root: Path
    ) -> None:
        manifest = root / "server" / MANIFEST
        path = binary(root / "custom-target", manifest)

        assert path.is_absolute()
        assert path.name == f"rust-server{'.exe' if os.name == 'nt' else ''}"

    def test_the_target_directory_comes_from_cargo(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest = root / "server" / MANIFEST
        expected = root / "custom-target"
        commands: list[list[str]] = []

        def metadata(
            command: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps({"target_directory": str(expected)}),
            )

        monkeypatch.setattr(otel_conformance_rust.subprocess, "run", metadata)

        assert target_directory(manifest) == expected
        assert commands[0][0:2] == ["cargo", "metadata"]
        assert commands[0][commands[0].index("--manifest-path") + 1] == str(
            manifest
        )

    def test_cargo_metadata_failure_is_a_layout_error(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest = root / "server" / MANIFEST

        def metadata(
            command: list[str], **options: object
        ) -> subprocess.CompletedProcess[str]:
            assert options["check"] is False
            return subprocess.CompletedProcess(
                command,
                101,
                stdout="",
                stderr="invalid Cargo.lock",
            )

        monkeypatch.setattr(otel_conformance_rust.subprocess, "run", metadata)

        with pytest.raises(LayoutError, match="invalid Cargo.lock"):
            target_directory(manifest)

    def test_non_json_cargo_metadata_is_a_layout_error(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manifest = root / "server" / MANIFEST

        def metadata(
            command: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="not JSON",
                stderr="",
            )

        monkeypatch.setattr(otel_conformance_rust.subprocess, "run", metadata)

        with pytest.raises(LayoutError, match="not JSON"):
            target_directory(manifest)

    def test_arguments_reach_the_scenario(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands: list[list[str]] = []
        monkeypatch.chdir(root / "server")
        monkeypatch.setattr(
            otel_conformance_rust,
            "target_directory",
            lambda _: root / "custom-target",
        )
        monkeypatch.setattr(
            otel_conformance_rust.subprocess,
            "call",
            lambda command: commands.append(command) or 0,
        )

        assert otel_conformance_rust.main(["run", "--flag", "value"]) == 0
        assert commands[0][1:] == ["--flag", "value"]

    def test_running_executes_what_building_produced(self, root: Path) -> None:
        manifest = root / "server" / MANIFEST
        target = root / "custom-target"

        assert run_command(target, manifest)[0] == str(binary(target, manifest))
