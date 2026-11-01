# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Regenerating every committed npm lockfile with the smallest change."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import otel_conformance_js
from otel_conformance_js import (
    CREATION_FLAGS,
    lock_projects,
    refresh_local_packages,
    relock,
    relock_command,
)

TRACKED = (
    "scenarios/http/js/package-lock.json",
    "tools/http/test-client/js/package-lock.json",
    # A manifest without a lockfile of its own is not a project to relock.
    "tools/js/scenario-sdk/package.json",
    # Only scenarios/ and tools/ are searched.
    "elsewhere/package-lock.json",
)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    for relative in TRACKED:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    subprocess.run(
        ["git", "init", "-q"],
        cwd=tmp_path,
        check=True,
        creationflags=CREATION_FLAGS,
    )
    subprocess.run(
        ["git", "add", "-A"],
        cwd=tmp_path,
        check=True,
        creationflags=CREATION_FLAGS,
    )
    # Untracked: a lockfile git does not know about is not the build's.
    untracked = tmp_path / "scenarios" / "scratch" / "package-lock.json"
    untracked.parent.mkdir(parents=True)
    untracked.write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], Path]]:
    recorded: list[tuple[list[str], Path]] = []

    def call(command: list[str], cwd: Path, creationflags: int) -> int:
        assert creationflags == (
            subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        recorded.append((command, Path(cwd)))
        return 0

    monkeypatch.setattr(otel_conformance_js.subprocess, "call", call)
    return recorded


def test_projects_are_the_tracked_lockfiles(repository: Path) -> None:
    assert lock_projects(repository) == [
        repository / "scenarios" / "http" / "js",
        repository / "tools" / "http" / "test-client" / "js",
    ]


def test_the_lock_is_rewritten_without_installing_or_running_scripts() -> None:
    command = relock_command()

    assert command[1:] == [
        "install",
        "--package-lock-only",
        "--ignore-scripts",
        "--no-audit",
        "--no-fund",
    ]


def test_every_project_is_relocked(
    repository: Path, calls: list[tuple[list[str], Path]]
) -> None:
    assert relock(repository) == 0
    assert [cwd for _, cwd in calls] == lock_projects(repository)


def test_copied_local_packages_are_refreshed_before_npm_runs(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository / "scenarios" / "http" / "js"
    path = project / "package-lock.json"
    packages = {
        "": {"name": "workspace"},
        "node_modules/local": {
            "resolved": "file:../../../tools/local",
            "dependencies": {"dependency": "1.0.0"},
        },
        "node_modules/linked": {
            "resolved": "file:../linked",
            "link": True,
        },
        "node_modules/dependency": {
            "version": "1.0.0",
            "resolved": "https://registry.npmjs.org/dependency/-/dependency-1.0.0.tgz",
            "integrity": "unchanged",
        },
    }
    path.write_text(json.dumps({"packages": packages}), encoding="utf-8")

    def call(command: list[str], cwd: Path, creationflags: int) -> int:
        if cwd == project:
            locked = json.loads(path.read_text(encoding="utf-8"))["packages"]
            assert "node_modules/local" not in locked
            assert locked == {
                name: package
                for name, package in packages.items()
                if name != "node_modules/local"
            }
        return 0

    monkeypatch.setattr(otel_conformance_js.subprocess, "call", call)

    assert relock(repository) == 0


def test_without_copied_packages_the_lockfile_is_untouched(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package-lock.json"
    original = '{"lockfileVersion": 3, "packages": {}}\n'
    path.write_text(original, encoding="utf-8")

    refresh_local_packages(tmp_path)

    assert path.read_text(encoding="utf-8") == original


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm is not on PATH")
def test_npm_reloads_local_manifests_and_relocks_without_churn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    shared = tmp_path / "shared"
    dependency = tmp_path / "dependency"
    for path, manifest in (
        (
            project,
            {
                "name": "project",
                "version": "1.0.0",
                "dependencies": {"shared": "file:../shared"},
            },
        ),
        (shared, {"name": "shared", "version": "1.0.0"}),
        (dependency, {"name": "dependency", "version": "2.0.0"}),
    ):
        path.mkdir()
        (path / "package.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
    (project / ".npmrc").write_text(
        "install-links=true\noffline=true\n", encoding="utf-8"
    )
    subprocess.run(
        relock_command(),
        cwd=project,
        check=True,
        capture_output=True,
        creationflags=CREATION_FLAGS,
    )
    (shared / "package.json").write_text(
        json.dumps(
            {
                "name": "shared",
                "version": "1.0.0",
                "dependencies": {
                    "dependency": f"file:{dependency.as_posix()}"
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        otel_conformance_js, "lock_projects", lambda root: [project]
    )

    assert relock(tmp_path) == 0
    lockfile = project / "package-lock.json"
    regenerated = lockfile.read_text(encoding="utf-8")
    packages = json.loads(regenerated)["packages"]
    assert packages["node_modules/shared"]["dependencies"] == {
        "dependency": f"file:{dependency.as_posix()}"
    }
    assert packages["node_modules/dependency"]["version"] == "2.0.0"
    assert relock(tmp_path) == 0
    assert lockfile.read_text(encoding="utf-8") == regenerated
    assert not (project / "node_modules").exists()


def test_the_first_failure_stops_the_run(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Path] = []

    def call(command: list[str], cwd: Path, creationflags: int) -> int:
        seen.append(Path(cwd))
        return 7

    monkeypatch.setattr(otel_conformance_js.subprocess, "call", call)

    assert relock(repository) == 7
    assert len(seen) == 1


@pytest.mark.parametrize("failure", [7, FileNotFoundError("npm")])
def test_unsuccessful_regeneration_restores_original_lock_bytes(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: int | FileNotFoundError,
) -> None:
    project = repository / "scenarios" / "http" / "js"
    lockfile = project / "package-lock.json"
    original = (
        b'{\r\n  "packages": {\r\n'
        b'    "node_modules/local": {"resolved": "file:../local"}\r\n'
        b"  }\r\n}\r\n"
    )
    lockfile.write_bytes(original)
    seen: list[Path] = []

    def call(command: list[str], cwd: Path, creationflags: int) -> int:
        seen.append(cwd)
        assert lockfile.read_bytes() != original
        lockfile.write_bytes(b"partial npm output")
        if isinstance(failure, FileNotFoundError):
            raise failure
        return failure

    monkeypatch.setattr(otel_conformance_js.subprocess, "call", call)

    if isinstance(failure, FileNotFoundError):
        with pytest.raises(FileNotFoundError, match="npm"):
            relock(repository)
    else:
        assert relock(repository) == failure
    assert lockfile.read_bytes() == original
    assert seen == [project]


def test_successful_regeneration_keeps_npm_output(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository / "scenarios" / "http" / "js"
    lockfile = project / "package-lock.json"

    def call(command: list[str], cwd: Path, creationflags: int) -> int:
        if cwd == project:
            lockfile.write_bytes(b'{"packages": {}}\n')
        return 0

    monkeypatch.setattr(otel_conformance_js.subprocess, "call", call)

    assert relock(repository) == 0
    assert lockfile.read_bytes() == b'{"packages": {}}\n'


def test_the_subcommand_relocks_the_current_repository(
    repository: Path,
    calls: list[tuple[list[str], Path]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(repository / "scenarios" / "http" / "js")

    assert otel_conformance_js.main(["relock"]) == 0
    assert len(calls) == 2


def test_outside_a_repository_says_so(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))

    assert otel_conformance_js.main(["relock"]) == 1
    assert "git repository" in capsys.readouterr().err
