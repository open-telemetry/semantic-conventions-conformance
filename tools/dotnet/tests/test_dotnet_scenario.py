# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The .NET toolchain a scenario directory no longer has to restate."""

from __future__ import annotations

from pathlib import Path

import pytest

import otel_conformance_dotnet
from otel_conformance_dotnet import (
    BUILD_MARKER,
    LayoutError,
    build_root,
    project_file,
    publish_command,
    run_command,
)

PROJECT = "OpenTelemetryAspNetCoreServer"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / BUILD_MARKER).write_text("", encoding="utf-8")
    return tmp_path


@pytest.fixture
def scenario(root: Path) -> Path:
    """A scenario directory, inside the project that produces it."""
    directory = root / "aspnetcore" / "opentelemetry-aspnetcore"
    (directory / "server").mkdir(parents=True)
    (directory / f"{PROJECT}.csproj").write_text("", encoding="utf-8")
    return directory / "server"


class TestFindingTheProject:
    def test_it_is_found_from_a_scenario_directory(
        self, scenario: Path
    ) -> None:
        """A scenario directory sits inside the project that produces it."""
        assert project_file(scenario).stem == PROJECT

    def test_the_project_directory_itself_counts(self, scenario: Path) -> None:
        assert project_file(scenario.parent).stem == PROJECT

    def test_being_outside_a_project_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LayoutError, match=r"\.csproj"):
            project_file(tmp_path)

    def test_a_directory_of_two_projects_says_so(self, root: Path) -> None:
        """Which one a scenario means would otherwise be a guess."""
        (root / "One.csproj").write_text("", encoding="utf-8")
        (root / "Two.csproj").write_text("", encoding="utf-8")

        with pytest.raises(LayoutError, match="exactly one project"):
            project_file(root)


class TestFindingTheBuild:
    def test_it_is_found_from_the_project(self, scenario: Path) -> None:
        """How deep a project sits is the layout's business, not its own."""
        assert build_root(scenario) == scenario.parents[2]

    def test_being_outside_a_build_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LayoutError, match=BUILD_MARKER):
            build_root(tmp_path)


class TestBuilding:
    def test_it_publishes_the_project(self, scenario: Path) -> None:
        project = project_file(scenario)

        command = publish_command(project)

        assert command[:2] == ["dotnet", "publish"]
        assert str(project) in command

    def test_it_leaves_the_output_path_to_the_build(
        self, scenario: Path
    ) -> None:
        """`PublishDir` chooses it, so nothing here can disagree with it."""
        command = publish_command(project_file(scenario))

        assert "--output" not in command
        assert "-o" not in command


class TestRunning:
    def test_it_runs_what_the_build_published(self, root: Path) -> None:
        command = run_command(root, root / f"{PROJECT}.csproj")

        assert command == [
            "dotnet",
            str(
                root
                / "artifacts"
                / "scenario-runtime"
                / PROJECT
                / f"{PROJECT}.dll"
            ),
        ]

    def test_the_runtime_is_the_builds_rather_than_the_projects(
        self, scenario: Path
    ) -> None:
        """Where a project sits on disk is the build's business."""
        root = build_root(scenario)

        command = run_command(root, project_file(scenario))

        assert command[1].startswith(
            str(root / "artifacts" / "scenario-runtime" / PROJECT)
        )

    def test_it_runs_the_assembly_rather_than_the_executable(
        self, root: Path
    ) -> None:
        """The executable's name is `.exe` on Windows and bare elsewhere."""
        command = run_command(root, root / f"{PROJECT}.csproj")

        assert command[1].endswith(".dll")

    def test_arguments_reach_the_scenario(self, root: Path) -> None:
        command = run_command(
            root, root / f"{PROJECT}.csproj", arguments=["--port", "8080"]
        )

        assert command[-2:] == ["--port", "8080"]


class TestTheCommandLine:
    @pytest.fixture
    def calls(
        self, scenario: Path, monkeypatch: pytest.MonkeyPatch
    ) -> list[list[str]]:
        """What `main` would have started, from a scenario directory."""
        commands: list[list[str]] = []
        monkeypatch.chdir(scenario)
        monkeypatch.setattr(
            otel_conformance_dotnet.subprocess,
            "call",
            lambda command: commands.append(command) or 0,
        )
        return commands

    def test_build_publishes_the_scenarios_project(
        self, calls: list[list[str]]
    ) -> None:
        assert otel_conformance_dotnet.main(["build"]) == 0
        assert calls[0][:2] == ["dotnet", "publish"]
        assert calls[0][2].endswith(f"{PROJECT}.csproj")

    def test_run_starts_what_build_published(
        self, calls: list[list[str]]
    ) -> None:
        assert otel_conformance_dotnet.main(["run"]) == 0
        assert calls[0][0] == "dotnet"
        assert calls[0][1].endswith(f"{PROJECT}.dll")

    def test_an_option_after_run_is_the_scenarios(
        self, calls: list[list[str]]
    ) -> None:
        """argparse would otherwise refuse it as an option of its own."""
        assert otel_conformance_dotnet.main(["run", "--port", "8080"]) == 0
        assert calls[0][-2:] == ["--port", "8080"]

    def test_a_failed_command_is_what_the_caller_sees(
        self, scenario: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A `setup:` step is judged by the status it exits with."""
        monkeypatch.chdir(scenario)
        monkeypatch.setattr(
            otel_conformance_dotnet.subprocess, "call", lambda command: 1
        )

        assert otel_conformance_dotnet.main(["build"]) == 1
