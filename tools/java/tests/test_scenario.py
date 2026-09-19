# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Java toolchain a scenario directory no longer has to restate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import otel_conformance_java
from otel_conformance_java import (
    AGENT_CONTROL_JAR,
    ARTIFACTS_FILE,
    BUILD_MARKER,
    SCENARIO_LAUNCHER,
    ArtifactMetadataError,
    LayoutError,
    build_root,
    gradle_command,
    java_command,
    prepare_runtime,
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

    @pytest.fixture
    def prepared_artifacts(self, root: Path) -> bytes:
        contents = (
            json.dumps(
                {
                    "schema_version": 1,
                    "generated_by": "otel-conformance-java prepare",
                    "artifacts": [
                        {
                            "role": "instrumentation_library",
                            "ecosystem": "maven",
                            "coordinate": (
                                "io.opentelemetry.javaagent:"
                                "opentelemetry-javaagent"
                            ),
                            "version": "2.31.1",
                        },
                        {
                            "role": "instrumented_library",
                            "ecosystem": "maven",
                            "coordinate": "com.linecorp.armeria:armeria",
                            "version": "1.41.1",
                        },
                    ],
                },
                indent=2,
            )
            + "\n"
        ).encode()
        runtime = root / "build" / "scenario-runtime" / RUNTIME
        runtime.mkdir(parents=True)
        (runtime / ARTIFACTS_FILE).write_bytes(contents)
        return contents

    def test_success_copies_prepared_artifacts_into_current_target(
        self,
        root: Path,
        tmp_path: Path,
        prepared_artifacts: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            otel_conformance_java.subprocess, "call", lambda _: 0
        )
        target = tmp_path / "target"
        target.mkdir()

        assert prepare_runtime(root, PROJECT, target) == 0

        assert (target / ARTIFACTS_FILE).read_bytes() == prepared_artifacts

    def test_failed_gradle_does_not_overwrite_committed_artifacts(
        self,
        root: Path,
        tmp_path: Path,
        prepared_artifacts: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        del prepared_artifacts
        monkeypatch.setattr(
            otel_conformance_java.subprocess, "call", lambda _: 1
        )
        target = tmp_path / "target"
        target.mkdir()
        committed = target / ARTIFACTS_FILE
        committed.write_bytes(b"committed\n")

        assert prepare_runtime(root, PROJECT, target) == 1
        assert committed.read_bytes() == b"committed\n"

    def test_missing_prepared_artifacts_does_not_overwrite_committed_file(
        self,
        root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            otel_conformance_java.subprocess, "call", lambda _: 0
        )
        target = tmp_path / "target"
        target.mkdir()
        committed = target / ARTIFACTS_FILE
        committed.write_bytes(b"committed\n")

        with pytest.raises(ArtifactMetadataError, match="missing"):
            prepare_runtime(root, PROJECT, target)

        assert committed.read_bytes() == b"committed\n"

    def test_missing_artifacts_remain_optional_for_an_unmigrated_target(
        self,
        root: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            otel_conformance_java.subprocess, "call", lambda _: 0
        )
        target = tmp_path / "target"
        target.mkdir()

        assert prepare_runtime(root, PROJECT, target) == 0
        assert not (target / ARTIFACTS_FILE).exists()

    @pytest.mark.parametrize("contents", ["{", "{}", "null", "[]"])
    def test_invalid_prepared_artifacts_does_not_overwrite_committed_file(
        self,
        root: Path,
        tmp_path: Path,
        prepared_artifacts: bytes,
        monkeypatch: pytest.MonkeyPatch,
        contents: str,
    ) -> None:
        del prepared_artifacts
        monkeypatch.setattr(
            otel_conformance_java.subprocess, "call", lambda _: 0
        )
        runtime = root / "build" / "scenario-runtime" / RUNTIME
        (runtime / ARTIFACTS_FILE).write_text(contents, encoding="utf-8")
        target = tmp_path / "target"
        target.mkdir()
        committed = target / ARTIFACTS_FILE
        committed.write_bytes(b"committed\n")

        with pytest.raises(ArtifactMetadataError, match="invalid artifact metadata"):
            prepare_runtime(root, PROJECT, target)

        assert committed.read_bytes() == b"committed\n"

    @pytest.mark.parametrize(
        "field,value",
        [
            ("schema_version", 2),
            ("schema_version", True),
            ("generated_by", None),
            ("artifacts", []),
            ("artifacts", {}),
            ("artifacts", [None]),
            ("role", None),
            ("role", []),
            ("ecosystem", "npm"),
            ("coordinate", ""),
            ("version", None),
            ("version", " "),
            ("version", 1),
        ],
    )
    def test_invalid_fields_do_not_overwrite_committed_artifacts(
        self,
        root: Path,
        tmp_path: Path,
        prepared_artifacts: bytes,
        monkeypatch: pytest.MonkeyPatch,
        field: str,
        value: object,
    ) -> None:
        monkeypatch.setattr(
            otel_conformance_java.subprocess, "call", lambda _: 0
        )
        metadata = json.loads(prepared_artifacts)
        entry = metadata if field in metadata else metadata["artifacts"][0]
        if value is None:
            del entry[field]
        else:
            entry[field] = value
        runtime = root / "build" / "scenario-runtime" / RUNTIME
        (runtime / ARTIFACTS_FILE).write_text(json.dumps(metadata))
        target = tmp_path / "target"
        target.mkdir()
        committed = target / ARTIFACTS_FILE
        committed.write_bytes(prepared_artifacts)

        with pytest.raises(ArtifactMetadataError, match="invalid artifact metadata"):
            prepare_runtime(root, PROJECT, target)

        assert committed.read_bytes() == prepared_artifacts

    def test_unchanged_artifacts_are_not_replaced(
        self,
        root: Path,
        tmp_path: Path,
        prepared_artifacts: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            otel_conformance_java.subprocess, "call", lambda _: 0
        )
        target = tmp_path / "target"
        target.mkdir()
        committed = target / ARTIFACTS_FILE
        committed.write_bytes(prepared_artifacts)
        original_inode = committed.stat().st_ino

        assert prepare_runtime(root, PROJECT, target) == 0
        assert committed.stat().st_ino == original_inode


class TestRunning:
    def test_an_agent_run_attaches_the_agent(self, root: Path) -> None:
        command = java_command(root, PROJECT, MAIN, agent=True)

        agent = (
            f"-javaagent:"
            f"{root / 'build' / 'scenario-runtime' / RUNTIME / 'agent'}"
        )
        assert any(argument.startswith(agent) for argument in command)
        extension = (
            root
            / "build"
            / "scenario-runtime"
            / RUNTIME
            / "agent"
            / AGENT_CONTROL_JAR
        )
        assert f"-Dotel.javaagent.extensions={extension}" in command

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
        assert command[-2:] == [SCENARIO_LAUNCHER, MAIN]

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

        assert command[-3:] == [SCENARIO_LAUNCHER, MAIN, "library"]

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
        assert commands[0][-2:] == [SCENARIO_LAUNCHER, MAIN]
