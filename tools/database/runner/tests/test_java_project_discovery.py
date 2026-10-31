# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from otel_conformance_java import gradle_command

pytestmark = pytest.mark.skipif(
    os.environ.get("OTEL_CONFORMANCE_TEST_JAVA_DISCOVERY") != "1",
    reason="set OTEL_CONFORMANCE_TEST_JAVA_DISCOVERY=1 to run Gradle integration tests",
)

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


def _projects(root: Path) -> set[str]:
    output = _gradle(root, "projects")
    return set(re.findall(r"Project '(:[^']+)'", output))


@pytest.fixture
def discovery_root(
    tmp_path: Path,
) -> Path:
    shutil.copyfile(DISCOVERY_SCRIPT, tmp_path / DISCOVERY_SCRIPT.name)
    (tmp_path / "settings.gradle.kts").write_text(
        'rootProject.name = "fixture"\n'
        f'apply(from = "{DISCOVERY_SCRIPT.name}")\n',
        encoding="utf-8",
    )
    return tmp_path


def test_discovers_owned_projects_and_prunes_excluded_trees(
    discovery_root: Path,
) -> None:
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
        build_file = discovery_root / project / "build.gradle.kts"
        build_file.parent.mkdir(parents=True, exist_ok=True)
        build_file.touch()

    excluded_trees = {
        "nested-build",
        "buildSrc",
        ".gradle",
        "build",
        "out",
        "target",
        "src/test/resources",
        "shared/jdbc/scenarios/src/test/resources",
        "bin",
        "shared/jdbc/scenarios/bin",
        "node_modules",
        "future-backend/new-client/node_modules",
        ".hidden",
        "shared/jdbc/scenarios/.hidden",
    }
    for tree in excluded_trees:
        build_file = discovery_root / tree / "fixture" / "build.gradle.kts"
        build_file.parent.mkdir(parents=True, exist_ok=True)
        build_file.touch()

    nested_build = discovery_root / "nested-build"
    (nested_build / "settings.gradle.kts").touch()

    projects = {
        project.replace(":", "/").lstrip("/")
        for project in _projects(discovery_root)
    }
    assert projects >= expected_projects
    for tree in excluded_trees:
        assert not any(
            project == tree or project.startswith(f"{tree}/")
            for project in projects
        )


def test_adding_a_project_invalidates_configuration_cache(
    discovery_root: Path,
) -> None:
    (discovery_root / "build.gradle").write_text(
        "tasks.register('projectSnapshot') {\n"
        "    inputs.property('projectPaths', rootProject.allprojects.collect { it.path }.sort())\n"
        "    doLast {\n"
        "        println('DISCOVERED=' + inputs.properties.projectPaths.join(','))\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    baseline = discovery_root / "baseline" / "build.gradle.kts"
    baseline.parent.mkdir()
    baseline.touch()
    # Gradle creates its report directory after settings evaluation.
    (discovery_root / "build").mkdir()

    output = _gradle(discovery_root, "projectSnapshot", "--configuration-cache")
    assert "DISCOVERED=:,:baseline" in output

    reused = _gradle(discovery_root, "projectSnapshot", "--configuration-cache")
    assert "Reusing configuration cache." in reused
    assert "DISCOVERED=:,:baseline" in reused

    added = discovery_root / "future-backend" / "client" / "build.gradle.kts"
    added.parent.mkdir(parents=True)
    added.touch()

    updated = _gradle(discovery_root, "projectSnapshot", "--configuration-cache")
    assert "Reusing configuration cache." not in updated
    assert "DISCOVERED=:,:baseline,:future-backend,:future-backend:client" in updated


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
        ":shared:mongodb:support",
        ":shared:mongodb:sync:scenarios",
        ":shared:mongodb:sync:opentelemetry-javaagent",
        ":shared:mongodb:sync:opentelemetry-library",
        ":shared:mongodb:async:scenarios",
        ":shared:mongodb:async:opentelemetry-javaagent",
        ":shared:mongodb:async:opentelemetry-library",
        ":shared:mongodb:reactive:scenarios",
        ":shared:mongodb:reactive:opentelemetry-javaagent",
        ":shared:mongodb:reactive:opentelemetry-library",
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
