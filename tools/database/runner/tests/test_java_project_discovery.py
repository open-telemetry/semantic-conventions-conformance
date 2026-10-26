# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from otel_conformance_java import gradle_command

REPO_ROOT = Path(__file__).resolve().parents[4]
SCENARIO_ROOT = REPO_ROOT / "scenarios/database/java"
DISCOVERY_SCRIPT = SCENARIO_ROOT / "discover-projects.gradle.kts"


def _gradle(root: Path, *arguments: str) -> str:
    command = gradle_command(SCENARIO_ROOT, arguments[0])
    command[command.index("--project-dir") + 1] = str(root)
    command.extend((*arguments[1:], "--no-daemon", "--console=plain"))
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW
        if sys.platform == "win32"
        else 0,
    )
    return result.stdout


@pytest.mark.parametrize(
    ("platform", "creationflags"),
    [("linux", 0), ("win32", 0x08000000)],
)
def test_gradle_uses_wrapper_main_and_platform_flags(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    creationflags: int,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="fixture output")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(
        subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False
    )

    assert _gradle(tmp_path, "projects", "--all") == "fixture output"

    command, kwargs = calls[0]
    expected_command = gradle_command(SCENARIO_ROOT, "projects")
    expected_command[expected_command.index("--project-dir") + 1] = str(
        tmp_path
    )
    expected_command.extend(("--all", "--no-daemon", "--console=plain"))
    assert command == expected_command
    assert "org.gradle.wrapper.GradleWrapperMain" in command
    assert str(SCENARIO_ROOT / "gradle/wrapper/gradle-wrapper.jar") in command
    assert kwargs["creationflags"] == creationflags


def _projects(root: Path) -> set[str]:
    output = _gradle(root, "projects")
    return set(re.findall(r"Project '(:[^']+)'", output))


def test_discovers_owned_projects_and_prunes_excluded_trees(
    tmp_path: Path,
) -> None:
    shutil.copyfile(DISCOVERY_SCRIPT, tmp_path / DISCOVERY_SCRIPT.name)
    (tmp_path / "settings.gradle.kts").write_text(
        'rootProject.name = "fixture"\n'
        f'apply(from = "{DISCOVERY_SCRIPT.name}")\n',
        encoding="utf-8",
    )

    expected_projects = {
        "shared/jdbc/scenarios",
        "shared/jdbc/opentelemetry-javaagent",
        "shared/jdbc/opentelemetry-library",
        "shared/redis/lettuce/scenarios",
        "shared/redis/lettuce/opentelemetry-javaagent",
        "shared/redis/lettuce/opentelemetry-library",
        "shared/redis/jedis/opentelemetry-javaagent",
        "shared/redis/rediscala/opentelemetry-javaagent",
        "shared/redis/redisson/opentelemetry-javaagent",
        "future-backend/new-client/opentelemetry-javaagent",
    }
    for project in expected_projects:
        build_file = tmp_path / project / "build.gradle.kts"
        build_file.parent.mkdir(parents=True, exist_ok=True)
        build_file.touch()

    excluded_projects = {
        "nested-build/child",
        "buildSrc/child",
        ".gradle/cache",
        "build/generated",
        "out/generated",
        "target/generated",
    }
    for project in excluded_projects:
        build_file = tmp_path / project / "build.gradle.kts"
        build_file.parent.mkdir(parents=True, exist_ok=True)
        build_file.touch()

    nested_build = tmp_path / "nested-build"
    (nested_build / "settings.gradle.kts").touch()

    projects = _projects(tmp_path)
    assert {project.replace(":", "/").lstrip("/") for project in projects} >= (
        expected_projects
    )
    assert not any(
        project.startswith(
            (
                ":nested-build",
                ":buildSrc",
                ":.gradle",
                ":build",
                ":out",
                ":target",
            )
        )
        for project in projects
    )


def test_preserves_database_project_names() -> None:
    projects = _projects(SCENARIO_ROOT)
    assert {
        ":scenario-support",
        ":scenario-sdk",
        ":agent-control",
        ":sql-test-client",
        ":shared:jdbc:scenarios",
        ":shared:jdbc:opentelemetry-javaagent",
        ":shared:jdbc:opentelemetry-library",
        ":shared:redis:lettuce:scenarios",
        ":shared:redis:lettuce:opentelemetry-javaagent",
        ":shared:redis:lettuce:opentelemetry-library",
        ":shared:redis:jedis:opentelemetry-javaagent",
        ":shared:redis:rediscala:opentelemetry-javaagent",
        ":shared:redis:redisson:opentelemetry-javaagent",
    } <= projects
    assert "prepareRuntime" in _gradle(
        SCENARIO_ROOT,
        ":shared:jdbc:opentelemetry-javaagent:tasks",
        "--all",
    )
