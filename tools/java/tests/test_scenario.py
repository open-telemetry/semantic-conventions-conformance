# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Java toolchain a scenario directory no longer has to restate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import otel_conformance_java
from otel_conformance_java import (
    AGENT_CONTROL_JAR,
    BUILD_MARKER,
    JAVA_RUNTIME,
    SCENARIO_LAUNCHER,
    LayoutError,
    RuntimePreparationError,
    build_root,
    gradle_command,
    java_command,
)

MAIN = "ArmeriaJavaagentServerScenario"
PROJECT = "armeria:opentelemetry-javaagent"
RUNTIME = "armeria-opentelemetry-javaagent"


def prepare_runtime(root: Path, project: str, version: int = 25) -> Path:
    executable = root / f"jdk {version}" / "bin" / "java.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.touch()
    executable.chmod(0o755)
    runtime = (
        root
        / otel_conformance_java.RUNTIME
        / project.strip(":").replace(":", "-")
    )
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / JAVA_RUNTIME).write_text(
        json.dumps(
            {"executable": str(executable), "languageVersion": version}
        ),
        encoding="utf-8",
    )
    return executable


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / BUILD_MARKER).write_text("", encoding="utf-8")
    prepare_runtime(tmp_path, PROJECT)
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

    def test_the_build_uses_java_home(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        executable = root / "jdk 25" / "bin" / "java.exe"
        monkeypatch.setenv("JAVA_HOME", str(executable.parent.parent))

        assert gradle_command(root, ":help")[0] == str(executable)

    def test_the_build_uses_path_without_java_home(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("JAVA_HOME", raising=False)

        assert gradle_command(root, ":help")[0] == "java"


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
        prepare_runtime(root, "okhttp:javaagent")
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
            root,
            PROJECT,
            MAIN,
            agent=False,
            arguments=["library", "--option", "value with spaces"],
        )

        assert command[-5:] == [
            SCENARIO_LAUNCHER,
            MAIN,
            "library",
            "--option",
            "value with spaces",
        ]

    def test_agent_attachment_is_not_an_application_argument(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands: list[list[str]] = []
        monkeypatch.setattr(otel_conformance_java, "build_root", lambda: root)
        monkeypatch.setattr(
            otel_conformance_java.subprocess,
            "call",
            lambda command, **kwargs: commands.append(command) or 0,
        )

        assert (
            otel_conformance_java.main(["run", "--agent", PROJECT, MAIN]) == 0
        )
        assert any(
            argument.startswith("-javaagent:") for argument in commands[0]
        )
        assert commands[0][-2:] == [SCENARIO_LAUNCHER, MAIN]

    @pytest.mark.parametrize(
        "project",
        ["helidon:opentelemetry-javaagent", "helidon:opentelemetry-library"],
    )
    def test_helidon_uses_prepared_java_27_with_build_java_25(
        self, root: Path, monkeypatch: pytest.MonkeyPatch, project: str
    ) -> None:
        build_java = root / "jdk 25" / "bin" / "java.exe"
        monkeypatch.setenv("JAVA_HOME", str(build_java.parent.parent))
        runtime_java = prepare_runtime(root, project, 27)

        assert gradle_command(root, f":{project}:prepareRuntime")[0] == str(
            build_java
        )
        assert java_command(root, project, MAIN, agent=False)[0] == str(
            runtime_java
        )
        assert java_command(root, PROJECT, MAIN, agent=False)[0] == str(
            build_java
        )

    def test_the_recorded_executable_is_one_argument_even_with_spaces(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JAVA_HOME", str(root / "unrelated jdk"))
        monkeypatch.setenv("PATH", "")

        command = java_command(root, f":{PROJECT}:", MAIN, agent=False)

        assert command[0] == str(root / "jdk 25" / "bin" / "java.exe")

    def test_run_inherits_the_fresh_environment_and_process_streams(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(otel_conformance_java, "build_root", lambda: root)
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:54321"
        )
        monkeypatch.setenv("OTEL_HTTP_SCENARIO_PORT", "54322")
        monkeypatch.setenv("JAVA_HOME", str(root / "jdk 25"))
        executable = prepare_runtime(root, "helidon:opentelemetry-library", 27)
        calls: list[tuple[list[str], dict[str, object]]] = []

        def call(command: list[str], **kwargs: object) -> int:
            calls.append((command, kwargs))
            assert (
                os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"]
                == "http://127.0.0.1:54321"
            )
            assert os.environ["OTEL_HTTP_SCENARIO_PORT"] == "54322"
            return 42

        monkeypatch.setattr(otel_conformance_java.subprocess, "call", call)

        assert (
            otel_conformance_java.main(
                ["run", "helidon:opentelemetry-library", MAIN, "--option"]
            )
            == 42
        )
        command, kwargs = calls[0]
        assert command[0] == str(executable)
        assert command[-3:] == [SCENARIO_LAUNCHER, MAIN, "--option"]
        assert kwargs == {
            "stdin": sys.stdin,
            "stdout": sys.stdout,
            "stderr": sys.stderr,
            "creationflags": (
                otel_conformance_java.subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0
            ),
        }

    def test_direct_process_preserves_stdin_output_environment_and_exit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:54321"
        )
        child = (
            "import os, sys; "
            "print(os.environ['OTEL_EXPORTER_OTLP_ENDPOINT']); "
            "print(sys.stdin.read()); "
            "print('diagnostic', file=sys.stderr); sys.exit(7)"
        )
        launcher = (
            "import sys\n"
            "from pathlib import Path\n"
            "import otel_conformance_java as java\n"
            "java.build_root = lambda: Path.cwd()\n"
            f"java.java_command = lambda *args, **kwargs: [sys.executable, '-c', {child!r}]\n"
            "sys.exit(java.main(['run', 'project', 'Main']))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", launcher],
            input="driver shutdown",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            ),
        )

        assert completed.returncode == 7
        assert completed.stdout.splitlines() == [
            "http://127.0.0.1:54321",
            "driver shutdown",
        ]
        assert completed.stderr.strip() == "diagnostic"


class TestRuntimeMetadata:
    def test_missing_metadata_requires_prepare_without_java_fallback(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JAVA_HOME", str(root / "jdk 25"))

        with pytest.raises(
            RuntimePreparationError,
            match="prepare helidon:opentelemetry-library",
        ):
            java_command(
                root, "helidon:opentelemetry-library", MAIN, agent=False
            )

    @pytest.mark.parametrize(
        "contents",
        [
            "",
            "{",
            "[]",
            "null",
            "{}",
        ],
    )
    def test_malformed_metadata_requires_prepare(
        self, root: Path, contents: str
    ) -> None:
        metadata = (
            root / otel_conformance_java.RUNTIME / RUNTIME / JAVA_RUNTIME
        )
        metadata.write_text(contents, encoding="utf-8")

        with pytest.raises(
            RuntimePreparationError, match=f"prepare {PROJECT}"
        ):
            java_command(root, PROJECT, MAIN, agent=False)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("executable", None),
            ("executable", 27),
            ("executable", ""),
            ("executable", "java"),
            ("languageVersion", None),
            ("languageVersion", "27"),
            ("languageVersion", True),
            ("languageVersion", 27.5),
            ("languageVersion", 0),
            ("languageVersion", -27),
        ],
    )
    def test_invalid_metadata_fields_require_prepare(
        self, root: Path, field: str, value: object
    ) -> None:
        metadata_file = (
            root / otel_conformance_java.RUNTIME / RUNTIME / JAVA_RUNTIME
        )
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        metadata[field] = value
        metadata_file.write_text(json.dumps(metadata), encoding="utf-8")

        with pytest.raises(
            RuntimePreparationError, match=f"prepare {PROJECT}"
        ):
            java_command(root, PROJECT, MAIN, agent=False)

    def test_invalid_utf8_requires_prepare(self, root: Path) -> None:
        metadata = (
            root / otel_conformance_java.RUNTIME / RUNTIME / JAVA_RUNTIME
        )
        metadata.write_bytes(b"\xff")

        with pytest.raises(
            RuntimePreparationError, match=f"prepare {PROJECT}"
        ):
            java_command(root, PROJECT, MAIN, agent=False)

    def test_removed_jdk_requires_prepare(self, root: Path) -> None:
        executable = root / "jdk 25" / "bin" / "java.exe"
        executable.unlink()

        with pytest.raises(
            RuntimePreparationError, match="Java 25 executable is unavailable"
        ):
            java_command(root, PROJECT, MAIN, agent=False)

    def test_directory_is_not_an_executable(self, root: Path) -> None:
        executable = root / "jdk 25" / "bin" / "java.exe"
        executable.unlink()
        executable.mkdir()

        with pytest.raises(
            RuntimePreparationError, match="executable is unavailable"
        ):
            java_command(root, PROJECT, MAIN, agent=False)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows does not use Unix execute permissions",
    )
    def test_non_executable_jdk_requires_prepare(self, root: Path) -> None:
        executable = root / "jdk 25" / "bin" / "java.exe"
        executable.chmod(0o644)

        with pytest.raises(
            RuntimePreparationError, match="executable is unavailable"
        ):
            java_command(root, PROJECT, MAIN, agent=False)

    def test_cli_reports_prepare_guidance_without_starting_java(
        self,
        root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(otel_conformance_java, "build_root", lambda: root)

        def unexpected_call(*args: object, **kwargs: object) -> int:
            pytest.fail("invalid runtime must not launch Java")

        monkeypatch.setattr(
            otel_conformance_java.subprocess, "call", unexpected_call
        )

        with pytest.raises(SystemExit) as error:
            otel_conformance_java.main(
                ["run", "helidon:opentelemetry-library", MAIN]
            )

        assert error.value.code == 1
        assert (
            "prepare helidon:opentelemetry-library" in capsys.readouterr().err
        )
