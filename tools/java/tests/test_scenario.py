# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Java toolchain a scenario directory no longer has to restate."""

from __future__ import annotations

from pathlib import Path

import otel_conformance_java
import pytest
from otel_conformance_java import (
    BUILD_MARKER,
    LayoutError,
    build_root,
    gradle_command,
    java_command,
)

MAIN = "ArmeriaJavaagentServerScenario"
PROJECT = "armeria:opentelemetry-javaagent"
RUNTIME = "armeria-opentelemetry-javaagent"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / BUILD_MARKER).write_text("", encoding="utf-8")
    return tmp_path


class TestFindingTheBuild:
    def test_it_is_found_from_a_scenario_directory(self, root: Path) -> None:
        """How deep a scenario sits is the layout's business, not its own."""
        scenario = root / "armeria" / "server" / "opentelemetry-javaagent"
        scenario.mkdir(parents=True)

        assert build_root(scenario) == root

    def test_the_build_root_itself_counts(self, root: Path) -> None:
        assert build_root(root) == root

    def test_being_outside_a_build_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LayoutError, match=BUILD_MARKER):
            build_root(tmp_path)


class TestPreparing:
    def test_it_runs_the_committed_wrapper(self, root: Path) -> None:
        command = gradle_command(root, f":{PROJECT}:prepareRuntime")

        wrapper = root / "gradle" / "wrapper" / "gradle-wrapper.jar"
        assert "org.gradle.wrapper.GradleWrapperMain" in command
        assert str(wrapper) in command
        assert command[-1] == f":{PROJECT}:prepareRuntime"

    def test_it_names_the_project_rather_than_relying_on_the_directory(
        self, root: Path
    ) -> None:
        """A scenario runs from its own directory, not the build's."""
        command = gradle_command(root, f":{PROJECT}:prepareRuntime")

        assert command[command.index("--project-dir") + 1] == str(root)


class TestRunning:
    def test_an_agent_run_attaches_the_agent(self, root: Path) -> None:
        command = java_command(root, PROJECT, MAIN, agent=True)

        agent = (
            f"-javaagent:"
            f"{root / 'build' / 'scenario-runtime' / RUNTIME / 'agent'}"
        )
        assert any(argument.startswith(agent) for argument in command)

    def test_a_nested_project_gets_its_own_runtime(self, root: Path) -> None:
        """Two libraries can both have a project called `javaagent`."""
        command = java_command(root, "okhttp:javaagent", MAIN, agent=False)

        classpath = command[command.index("-classpath") + 1]
        assert classpath.startswith(
            str(root / "build" / "scenario-runtime" / "okhttp-javaagent")
        )

    def test_the_runtime_is_the_builds_rather_than_the_projects(
        self, root: Path
    ) -> None:
        """Where a Gradle project sits on disk is the build's business."""
        command = java_command(root, PROJECT, MAIN, agent=False)

        classpath = command[command.index("-classpath") + 1]
        assert classpath.startswith(
            str(root / "build" / "scenario-runtime" / RUNTIME)
        )

    def test_a_run_without_the_agent_does_not_attach_it(
        self, root: Path
    ) -> None:
        command = java_command(root, PROJECT, MAIN, agent=False)

        assert not any(
            argument.startswith("-javaagent:") for argument in command
        )

    def test_it_runs_java_rather_than_gradle(self, root: Path) -> None:
        """A long-lived Gradle daemon would serve a stale OTLP endpoint."""
        command = java_command(root, PROJECT, MAIN, agent=True)

        assert "org.gradle.wrapper.GradleWrapperMain" not in command
        assert command[-1] == MAIN

    def test_the_classpath_is_whatever_the_library_resolved(
        self, root: Path
    ) -> None:
        command = java_command(root, PROJECT, MAIN, agent=False)

        classpath = command[command.index("-classpath") + 1]
        assert classpath.endswith("*")

    def test_arguments_reach_the_scenario(self, root: Path) -> None:
        command = java_command(
            root, PROJECT, MAIN, agent=False, arguments=["library"]
        )

        assert command[-1] == "library"

    def test_agent_attachment_is_not_an_application_argument(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands: list[list[str]] = []
        monkeypatch.setattr(otel_conformance_java, "build_root", lambda: root)
        monkeypatch.setattr(
            otel_conformance_java.subprocess,
            "call",
            lambda command: commands.append(command) or 0,
        )

        assert (
            otel_conformance_java.main(["run", "--agent", PROJECT, MAIN]) == 0
        )
        assert any(
            argument.startswith("-javaagent:") for argument in commands[0]
        )
        assert commands[0][-1] == MAIN
