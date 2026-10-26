# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
SCENARIO_ROOT = REPO_ROOT / "scenarios/database/java"
DISCOVERY_SCRIPT = SCENARIO_ROOT / "discover-projects.gradle.kts"
GRADLEW = SCENARIO_ROOT / "gradlew"


def _gradle(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        [
            str(GRADLEW),
            "-p",
            str(root),
            *arguments,
            "--no-daemon",
            "--console=plain",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return result.stdout


def _projects(root: Path) -> set[str]:
    output = _gradle(root, "projects")
    return set(re.findall(r"Project '(:[^']+)'", output))


def test_discovers_owned_projects_and_prunes_excluded_trees(
    tmp_path: Path,
) -> None:
    (tmp_path / "settings.gradle.kts").write_text(
        f'rootProject.name = "fixture"\napply(from = "{DISCOVERY_SCRIPT}")\n',
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
            (":nested-build", ":buildSrc", ":.gradle", ":build", ":out", ":target")
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
