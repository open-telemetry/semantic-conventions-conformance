# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from opentelemetry.conformance import _scenario_matrix
from opentelemetry.conformance._scenario_matrix import SHARD_COUNTS, matrix

REPO = Path(__file__).resolve().parents[3]


def run_subprocess(
    args: Sequence[str],
    *,
    input: str | None = None,
    capture_output: bool = False,
    check: bool = False,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    stdout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input,
        capture_output=capture_output,
        text=True,
        check=check,
        cwd=cwd,
        env=env,
        stdout=stdout,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


@pytest.mark.parametrize(
    ("platform", "creationflags"),
    [("win32", 0x08000000), ("linux", 0)],
)
def test_run_subprocess_uses_platform_creation_flags(
    monkeypatch: pytest.MonkeyPatch, platform: str, creationflags: int
) -> None:
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(
        subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False
    )
    result = subprocess.CompletedProcess(["command"], 0, "output", "")
    run = Mock(return_value=result)
    monkeypatch.setattr(subprocess, "run", run)

    actual = run_subprocess(["command"], input="input")

    assert actual is result
    run.assert_called_once()
    assert run.call_args.args == (["command"],)
    assert run.call_args.kwargs["input"] == "input"
    assert run.call_args.kwargs["creationflags"] == creationflags


def scenario_paths(group: str, libraries: list[str]) -> list[str]:
    return [
        f"scenarios/{group}/{library}/{instrumentation}/{variant}/conformance.yaml"
        for library in libraries
        for instrumentation in ("native", "instrumented")
        for variant in ("client", "server")
    ]


@pytest.mark.parametrize("group", ["gen-ai/python", "http/java"])
def test_sorted_round_robin_keeps_all_library_variants(group: str) -> None:
    libraries = ["zebra", "beta", "delta", "alpha", "gamma", "epsilon"]
    paths = scenario_paths(group, libraries)
    jobs = matrix(paths)["include"]
    assert jobs == matrix(reversed(paths + paths))["include"]
    assert len(jobs) == 4
    assert len({job["matrix_id"] for job in jobs}) == 4
    selected: list[str] = []
    for index, job in enumerate(jobs):
        roots = job["scenario_roots"].splitlines()
        assert roots == [
            f"scenarios/{group}/{library}"
            for library in sorted(libraries)[index::4]
        ]
        selected.extend(
            path for path in paths if any(path.startswith(r + "/") for r in roots)
        )
        assert job["cache_dependency_glob"].splitlines() == [
            f"{root}/**/uv.lock" for root in roots
        ]
        assert job["report_paths"].splitlines() == [
            f"{root}/**/output/weaver-reports/*.json" for root in roots
        ]
    assert Counter(selected) == Counter(paths)


@pytest.mark.parametrize("count", [1, 2, 3, 8])
def test_only_the_count_needs_to_change(count: int) -> None:
    libraries = ["a", "b", "c", "d", "e"]
    jobs = matrix(
        scenario_paths("http/java", libraries), {"http-java": count}
    )["include"]
    assert len(jobs) == min(count, len(libraries))
    assert [job["scenario_roots"].splitlines() for job in jobs] == [
        [f"scenarios/http/java/{name}" for name in libraries[index::count]]
        for index in range(min(count, len(libraries)))
    ]


def test_empty_groups_do_not_launch_jobs() -> None:
    assert matrix([]) == {"include": []}
    jobs = matrix(scenario_paths("http/python", ["a"]))["include"]
    assert [job["matrix_id"] for job in jobs] == ["http-python"]


@pytest.mark.parametrize("count", [0, -1, True, 1.5, "4", None])
def test_invalid_counts_fail_even_for_absent_groups(count: object) -> None:
    with pytest.raises(ValueError, match="invalid shard count"):
        matrix([], {"http-java": count})  # type: ignore[dict-item]


def test_other_groups_and_ruby_keep_their_existing_grouping() -> None:
    paths = scenario_paths("database/java", ["a", "b"])
    paths += scenario_paths("http/ruby", ["a", "b"])
    jobs = matrix(paths)["include"]
    assert jobs[0]["matrix_id"] == "database-java"
    assert jobs[0]["scenario_roots"] == "scenarios/database/java"
    assert [job["scenario_roots"] for job in jobs[1:]] == sorted(
        path.removesuffix("/conformance.yaml")
        for path in paths
        if "/ruby/" in path
    )
    for job in jobs[1:]:
        assert job["matrix_id"] == job["scenario_roots"].removeprefix(
            "scenarios/"
        ).replace("/", "-")


@pytest.mark.parametrize(
    "path",
    [
        "conformance.yaml",
        "elsewhere/http/java/a/conformance.yaml",
        "scenarios/http/java/conformance.yaml",
        "scenarios/http/java/../conformance.yaml",
    ],
)
def test_malformed_paths_fail(path: str) -> None:
    with pytest.raises(ValueError):
        matrix([path])


@pytest.mark.parametrize("paths", ["", "invalid\n"])
def test_cli_rejects_empty_or_invalid_discovery(paths: str) -> None:
    result = run_subprocess(
        [sys.executable, "-I", str(_scenario_matrix.__file__)],
        input=paths,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr
    assert not result.stdout


def test_tracked_scenarios_are_covered_once_by_standalone_cli() -> None:
    paths = run_subprocess(
        ["git", "ls-files", "scenarios/**/conformance.yaml"],
        cwd=REPO,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout.splitlines()
    result = run_subprocess(
        [sys.executable, "-I", str(_scenario_matrix.__file__)],
        input="\n".join(paths),
        capture_output=True,
        check=True,
    )
    jobs = json.loads(result.stdout)["include"]
    assert len({job["matrix_id"] for job in jobs}) == len(jobs)
    for group, count in SHARD_COUNTS.items():
        assert sum(job["matrix_id"].startswith(group + "-shard-") for job in jobs) == count
    covered = [
        path
        for job in jobs
        for root in job["scenario_roots"].splitlines()
        for path in paths
        if path.startswith(root + "/")
    ]
    assert Counter(covered) == Counter(paths)


@pytest.mark.skipif(sys.platform == "win32", reason="Scenario jobs run on Ubuntu")
def test_workflow_executes_and_patches_only_assigned_roots(tmp_path: Path) -> None:
    workflow = yaml.safe_load((REPO / ".github/workflows/runner.yml").read_text())
    steps = {step["name"]: step for step in workflow["jobs"]["scenarios"]["steps"]}
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> str:
        return run_subprocess(
            ["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE
        ).stdout

    paths = scenario_paths("http/java", ["a", "b", "c", "d", "e"])
    for path in paths:
        directory = repo / Path(path).parent
        directory.mkdir(parents=True)
        (directory / "conformance.yaml").touch()
        (directory / "data.json").write_text("{}\n")
    git("init")
    git("add", ".")
    git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "initial")

    env = {
        **os.environ,
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_OUTPUT": str(tmp_path / "outputs"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "RUN_LOG": str(tmp_path / "runs"),
    }

    def run_step(name: str, prefix: str = "") -> subprocess.CompletedProcess[str]:
        return run_subprocess(
            ["bash", "-e", "-c", prefix + steps[name]["run"]],
            cwd=repo,
            env=env,
            capture_output=True,
            check=False,
        )

    # One failing directory must not stop the remaining serial executions.
    stub = """
    otel-conformance() {
      echo "$1" >> "$RUN_LOG"
      printf '{"updated":true}\\n' > "$1/data.json"
      [[ "$1" != */a/native/client ]]
    }
    """
    patches: list[str] = []
    for index, job in enumerate(matrix(paths)["include"]):
        env["SCENARIO_ROOTS"] = job["scenario_roots"]
        patch = tmp_path / f"data-{index}.patch"
        env["DATA_PATCH"] = str(patch)
        result = run_step("Run scenarios", stub)
        assert result.returncode == (1 if index == 0 else 0), result.stderr
        assert run_step("Create the generated data patch").returncode == 0
        assert patch.stat().st_size > 0
        patches.append(str(patch))
        assert run_step("Check the committed coverage is up to date").returncode == 1

    runs = (tmp_path / "runs").read_text().splitlines()
    assert Counter(runs) == Counter(str(Path(path).parent) for path in paths)
    git("reset", "--hard", "HEAD")
    # Renovate applies all data patches together: overlap would fail here.
    git("apply", "--index", *patches)
    assert set(git("diff", "--cached", "--name-only").splitlines()) == {
        str(Path(path).parent / "data.json") for path in paths
    }
    assert run_step("Check the committed lock files are up to date").returncode == 1
