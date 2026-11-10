# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Resolving a registry into the coverage model used by reductions."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import pytest

from opentelemetry.conformance import _model

_PROCESS_MODELS = _model._process_models  # noqa: SLF001


@pytest.fixture(autouse=True)
def process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[], Path]:
    """Where this process keeps the models it returns, under ``tmp_path``.

    Calling it starts another process, with a directory of its own.
    """
    directories: list[Path] = []

    def start() -> Path:
        directory = tmp_path / f"process-{len(directories)}"
        directory.mkdir()
        directories.append(directory)
        return directory

    start()
    monkeypatch.setattr(_model, "_process_models", lambda: directories[-1])
    return start


def test_resolution_invokes_weaver_without_a_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands: list[list[str]] = []

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        generated = Path(command[-1])
        (generated / "coverage-model.json").write_text('{"spans": {}}')
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model, "check_weaver", lambda: None)
    monkeypatch.setattr(_model.subprocess, "run", run)
    registry = tmp_path / "registry"
    output = tmp_path / "cache" / "model.json"

    assert _model.resolve(registry, output) == output
    assert json.loads(output.read_text()) == {"spans": {}}
    assert len(commands) == 1
    assert commands[0][:-1] == [
        "weaver",
        "registry",
        "generate",
        "--quiet",
        "--v2",
        "--follow-symlinks=false",
        "--include-unreferenced=false",
        "--registry",
        str(registry),
        "--templates",
        str(_model._TEMPLATES),  # noqa: SLF001
        "coverage-model",
    ]
    assert not Path(commands[0][-1]).exists()


@pytest.mark.parametrize(
    "cache", ["external", "nested", "nested-relative", "parent"]
)
@pytest.mark.parametrize(
    "relative_registry", [False, True], ids=["absolute", "dot"]
)
@pytest.mark.parametrize(
    "change",
    [
        lambda registry: (registry / "spans.yaml").write_text("groups: [x]\n"),
        lambda registry: (registry / "metrics.yaml").unlink(),
        lambda registry: (registry / "metrics.yaml").rename(
            registry / "token-metrics.yaml"
        ),
    ],
    ids=["edited", "deleted", "renamed"],
)
def test_a_registry_is_resolved_again_only_when_its_files_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: Callable[[Path], object],
    cache: str,
    relative_registry: bool,
) -> None:
    runs: list[list[str]] = []

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        runs.append(command)
        (Path(command[-1]) / "coverage-model.json").write_text("{}")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model, "check_weaver", lambda: None)
    monkeypatch.setattr(_model.subprocess, "run", run)
    registry = tmp_path / "model"
    registry.mkdir()
    (registry / "spans.yaml").write_text("groups: []\n")
    (registry / "metrics.yaml").write_text("groups: []\n")
    cache_path = {
        "external": tmp_path / "cache",
        "nested": registry / ".cache" / "semconv",
        "nested-relative": registry / ".cache" / "semconv",
        "parent": tmp_path,
    }[cache]
    monkeypatch.chdir(registry)
    monkeypatch.setenv(
        "SEMCONV_CACHE",
        str(cache_path.relative_to(registry))
        if cache == "nested-relative"
        else str(cache_path),
    )
    if relative_registry:
        registry = Path(".")

    first = _model.coverage_model_for(registry)
    assert _model.coverage_model_for(registry) == first
    assert len(runs) == 1

    if cache in {"nested", "nested-relative"}:
        for name in (
            "advice-policies/domain/default.rego",
            "weaver-config/domain.toml",
            "advice-data/extra.json",
        ):
            generated = cache_path / name
            generated.parent.mkdir(parents=True, exist_ok=True)
            generated.write_text("generated output\n")
            assert _model.coverage_model_for(registry) == first
            assert len(runs) == 1

    change(registry)

    second = _model.coverage_model_for(registry)
    assert second != first
    assert len(runs) == 2
    assert second.name.startswith("model-")
    assert sorted(second.parent.iterdir()) == sorted([first, second])


@pytest.fixture
def weaver_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> list[list[str]]:
    """Weaver stubbed out, the cache outside the registry, and what ran."""
    runs: list[list[str]] = []

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        runs.append(command)
        (Path(command[-1]) / "coverage-model.json").write_text("{}")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model, "check_weaver", lambda: None)
    monkeypatch.setattr(_model.subprocess, "run", run)
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)
    return runs


def _registry(path: Path, manifest: str | None = None) -> Path:
    path.mkdir(parents=True)
    (path / "spans.yaml").write_text("groups: []\n")
    if manifest is not None:
        (path / "manifest.yaml").write_text(manifest)
    return path


def test_a_cache_that_is_the_registry_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _registry(tmp_path / "model")
    monkeypatch.setenv("SEMCONV_CACHE", str(registry))

    with pytest.raises(RuntimeError, match="SEMCONV_CACHE"):
        _model.coverage_model_for(registry)


@pytest.mark.parametrize(
    "cache",
    ["model/cache", "model/cache/semconv", "model/spans/.cache", "core/cache"],
)
def test_a_cache_weaver_would_read_is_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    weaver_runs: list[list[str]],
    cache: str,
) -> None:
    _registry(tmp_path / "core")
    registry = _registry(
        tmp_path / "model",
        "name: demo\n"
        "schema_url: https://example.com/schemas/demo/1.0.0\n"
        "dependencies:\n"
        "  - schema_url: https://example.com/schemas/core/1.0.0\n"
        "    registry_path: ../core\n",
    )
    monkeypatch.chdir(registry)
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / cache))

    if cache == "model/spans/.cache":
        # A hidden folder is one weaver skips.
        _model.coverage_model_for(registry)
        assert len(weaver_runs) == 1
        return
    with pytest.raises(RuntimeError, match="SEMCONV_CACHE"):
        _model.coverage_model_for(registry)
    assert weaver_runs == []


def test_a_model_of_files_that_changed_while_weaver_read_them_stays_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = _registry(tmp_path / "model")
    runs: list[str] = []

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if not runs:
            # Saved in an editor while weaver is reading the registry.
            (registry / "spans.yaml").write_text("groups: [b]\n")
        runs.append((registry / "spans.yaml").read_text())
        model = json.dumps({"read": runs[-1]})
        (Path(command[-1]) / "coverage-model.json").write_text(model)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model, "check_weaver", lambda: None)
    monkeypatch.setattr(_model.subprocess, "run", run)
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)

    first = _model.coverage_model_for(registry)
    assert json.loads(first.read_text()) == {"read": "groups: [b]\n"}
    stored = tmp_path / "cache" / "coverage-models" / "working-trees"
    assert not list(stored.glob("*.json"))

    second = _model.coverage_model_for(registry)
    assert json.loads(second.read_text()) == {"read": "groups: [b]\n"}
    assert len(runs) == 2

    (registry / "spans.yaml").write_text("groups: []\n")

    third = _model.coverage_model_for(registry)
    assert json.loads(third.read_text()) == {"read": "groups: []\n"}
    assert len(runs) == 3
    assert first.is_file()


def test_files_weaver_does_not_read_leave_the_model_alone(
    tmp_path: Path, weaver_runs: list[list[str]]
) -> None:
    registry = _registry(tmp_path / "model")
    first = _model.coverage_model_for(registry)

    for name, content in [
        (".git/objects/ab/cdef", b"blob"),
        (".git/config.yaml", b"x: 1\n"),
        (".venv/lib/site.yaml", b"x: 1\n"),
        (".spans.yaml.swp", b"swap"),
        ("__pycache__/x.pyc", b"\0"),
        ("README.md", b"# notes\n"),
    ]:
        path = registry / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    assert _model.coverage_model_for(registry) == first
    assert len(weaver_runs) == 1


def test_a_symlinked_folder_is_left_out_as_weaver_leaves_it(
    tmp_path: Path, weaver_runs: list[list[str]]
) -> None:
    shared = _registry(tmp_path / "common" / "model")
    registry = _registry(tmp_path / "model")
    try:
        (registry / "shared").symlink_to(shared, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available here")
    (shared / "loop").symlink_to(shared, target_is_directory=True)
    first = _model.coverage_model_for(registry)

    (shared / "spans.yaml").write_text("groups: [x]\n")
    assert _model.coverage_model_for(registry) == first

    (registry / "shared").unlink()
    shutil.copytree(shared, registry / "shared", symlinks=True)

    assert _model.coverage_model_for(registry) != first
    assert len(weaver_runs) == 2


def test_a_link_to_a_missing_file_is_skipped_as_weaver_skips_it(
    tmp_path: Path, weaver_runs: list[list[str]]
) -> None:
    registry = _registry(tmp_path / "model")
    first = _model.coverage_model_for(registry)
    try:
        (registry / "stale.yaml").symlink_to(tmp_path / "removed.yaml")
    except OSError:
        pytest.skip("symlinks are not available here")

    assert _model.coverage_model_for(registry) == first
    assert len(weaver_runs) == 1


def test_a_local_dependency_is_part_of_the_key(
    tmp_path: Path, weaver_runs: list[list[str]]
) -> None:
    core = _registry(tmp_path / "core")
    registry = _registry(
        tmp_path / "model",
        "name: demo\n"
        "schema_url: https://example.com/schemas/demo/1.0.0\n"
        "dependencies:\n"
        "  - schema_url: https://example.com/schemas/core/1.0.0\n"
        "    registry_path: ./core\n",
    )
    first = _model.coverage_model_for(registry)
    assert _model.coverage_model_for(registry) == first

    (core / "spans.yaml").write_text("groups: [x]\n")

    assert _model.coverage_model_for(registry) != first
    assert len(weaver_runs) == 2


_DEPENDENCIES = [
    "https://github.com/o/semconv.git@" + "a" * 40 + "[model]",
    "https://github.com/o/semconv.git@" + "A" * 40,
    "https://github.com/o/semconv.git@v1.44.0[model]",
    "https://github.com/o/semconv@v1.44.0[model]",
    "https://github.com/o/semconv.git@1.44.0",
    "https://github.com/o/semconv.git@main[model]",
    "https://github.com/o/semconv.git@" + "a" * 12 + "[model]",
    "https://github.com/o/semconv.git[model]",
    "https://example.com/semconv-1.44.0.tar.gz[model]",
    "https://example.com/latest.tar.gz[model]",
    "https://example.com/latest.zip",
    "core.zip[model]",
    None,
]
_IDS = [
    "commit",
    "commit-upper",
    "tag",
    "tag-no-git",
    "tag-bare",
    "branch",
    "short-commit",
    "default-branch",
    "versioned-archive",
    "latest-archive",
    "latest-zip",
    "local-archive",
    "schema-url-only",
]


def _depending_on(path: Path, registry_path: str | None) -> Path:
    return _registry(
        path,
        "name: demo\n"
        "schema_url: https://example.com/schemas/demo/1.0.0\n"
        "dependencies:\n"
        "  - schema_url: https://example.com/schemas/core/1.44.0\n"
        + (
            f"    registry_path: {registry_path}\n"
            if registry_path is not None
            else ""
        ),
    )


@pytest.mark.parametrize("registry_path", _DEPENDENCIES, ids=_IDS)
def test_a_dependency_that_can_move_is_resolved_every_time(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    registry_path: str | None,
) -> None:
    """Nothing is cached for it; each call gets this process's own copy."""
    (tmp_path / "core.zip").write_bytes(b"PK")
    registry = _depending_on(tmp_path / "model", registry_path)

    first = _model.coverage_model_for(registry)
    second = _model.coverage_model_for(registry)

    assert second == first
    assert len(weaver_runs) == 2
    assert "-unpinned-" in first.name
    assert sorted(first.parent.iterdir()) == [first]
    assert not (tmp_path / "cache").exists()


def test_a_dependency_that_can_move_is_found_before_any_definition_is_read(
    tmp_path: Path,
    weaver_runs: list[list[str]],  # noqa: ARG001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _depending_on(tmp_path / "core", "https://example.com/latest.zip")
    registry = _depending_on(tmp_path / "model", "./core")
    read: list[Path] = []
    definitions = _model._definitions  # noqa: SLF001

    def reading(root: Path, cache: Path) -> list[tuple[str, Path]]:
        read.append(root)
        return definitions(root, cache)

    monkeypatch.setattr(_model, "_definitions", reading)

    assert _model._digest(registry) is None  # noqa: SLF001
    assert read == []


_PUBLICATION = (
    "file_format: manifest/2.0\n"
    "schema_url: https://example.com/schemas/core/1.44.0\n"
    "resolved_registry_uri: {uri}\n"
)


@pytest.mark.parametrize(
    "uri", ["https://example.com/resolved.yaml", "../resolved.json"]
)
@pytest.mark.parametrize("published", ["registry", "dependency"])
def test_a_published_registry_is_resolved_every_time(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    published: str,
    uri: str,
) -> None:
    """Weaver reads the resolved registry it points at, wherever that is."""
    manifest = _PUBLICATION.format(uri=uri)
    if published == "registry":
        registry = _registry(tmp_path / "model", manifest)
    else:
        _registry(tmp_path / "core", manifest)
        registry = _depending_on(tmp_path / "model", "./core")

    first = _model.coverage_model_for(registry)

    assert _model.coverage_model_for(registry) == first
    assert len(weaver_runs) == 2
    assert "-unpinned-" in first.name
    assert not (tmp_path / "cache").exists()


def test_a_dependency_on_a_manifest_file_is_resolved_every_time(
    tmp_path: Path, weaver_runs: list[list[str]]
) -> None:
    _registry(tmp_path / "core", _PUBLICATION.format(uri="../resolved.json"))
    registry = _depending_on(tmp_path / "model", "./core/manifest.yaml")

    first = _model.coverage_model_for(registry)

    assert _model.coverage_model_for(registry) == first
    assert len(weaver_runs) == 2
    assert "-unpinned-" in first.name
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("pin", [None, "semconv-v1-model"])
def test_schema_url_overrides_keep_every_model_out_of_the_cache(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    pin: str | None,
) -> None:
    registry = _registry(tmp_path / "model")
    project = tmp_path / "project"
    (project / "nested").mkdir(parents=True)
    (project / ".weaver.toml").write_text(
        "[resolve.schema_url_overrides]\n"
        '"https://example.com/schemas/core/1.44.0" = "../core"\n'
    )
    monkeypatch.chdir(project / "nested")

    first = _model.coverage_model_for(registry, pin=pin)

    assert _model.coverage_model_for(registry, pin=pin) == first
    assert len(weaver_runs) == 2
    assert not (tmp_path / "cache").exists()


def _changing_weaver(
    monkeypatch: pytest.MonkeyPatch, models: list[dict[str, int]]
) -> None:
    """Weaver stubbed to write each of ``models`` in turn."""

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        model = models.pop(0)
        (Path(command[-1]) / "coverage-model.json").write_text(
            json.dumps(model)
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model.subprocess, "run", run)


@pytest.mark.parametrize("registry_path", _DEPENDENCIES, ids=_IDS)
def test_a_dependency_that_moved_gives_its_new_model(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    registry_path: str | None,
) -> None:
    """A moved tag, branch or archive changes the model, not the YAML here."""
    (tmp_path / "core.zip").write_bytes(b"PK")
    registry = _depending_on(tmp_path / "model", registry_path)
    _changing_weaver(monkeypatch, [{"version": 1}, {"version": 2}])

    first = _model.coverage_model_for(registry)
    second = _model.coverage_model_for(registry)

    assert _model.load(second) == {"version": 2}
    assert _model.load(first) == {"version": 1}


def test_a_commit_that_depends_on_a_branch_gives_the_branchs_new_model(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B at a fixed commit depends on C at ``main``, which moves."""
    b_url = "https://github.com/o/b.git"
    c_url = "https://github.com/o/c.git"
    remote = {
        b_url: tmp_path / "remote" / "b",
        c_url: tmp_path / "remote" / "c",
    }
    _depending_on(remote[b_url], f"{c_url}@main[model]")
    _registry(remote[c_url])
    (remote[c_url] / "version").write_text("1")
    registry = _depending_on(tmp_path / "model", f"{b_url}@{'a' * 40}[model]")

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Weaver resolving each dependency's own dependencies in turn."""
        weaver_runs.append(command)
        current = Path(command[command.index("--registry") + 1])
        while (current / "manifest.yaml").is_file():
            (dependency,) = _model._dependencies(current)  # noqa: SLF001
            current = remote[dependency["registry_path"].partition("@")[0]]
        (Path(command[-1]) / "coverage-model.json").write_text(
            json.dumps({"version": int((current / "version").read_text())})
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model.subprocess, "run", run)

    first = _model.coverage_model_for(registry)
    (remote[c_url] / "version").write_text("2")
    second = _model.coverage_model_for(registry)

    assert len(weaver_runs) == 2
    assert _model.load(first) == {"version": 1}
    assert _model.load(second) == {"version": 2}


def test_a_model_still_open_elsewhere_is_never_passed_off_as_refreshed(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows refuses to replace a file another run has open."""
    registry = _depending_on(
        tmp_path / "model", "https://github.com/o/semconv.git@main[model]"
    )
    _changing_weaver(monkeypatch, [{"version": 1}, {"version": 2}])
    replace = _model.os.replace

    def locked(source: str, target: Path) -> None:
        if Path(target).exists():
            raise PermissionError(13, "The process cannot access the file")
        replace(source, target)

    monkeypatch.setattr(_model.os, "replace", locked)

    first = _model.coverage_model_for(registry)
    second = _model.coverage_model_for(registry)

    assert second != first
    assert _model.load(second) == {"version": 2}
    assert _model.load(first) == {"version": 1}


@pytest.mark.parametrize("existing", [False, True])
def test_a_model_windows_will_not_replace_stands_unless_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,  # noqa: FBT001
) -> None:
    """A file under the same name holds the model already resolved for it."""
    output = tmp_path / "models" / "m.json"
    output.parent.mkdir()
    if existing:
        output.write_text("{ }")

    def locked(source: str, target: Path) -> None:
        raise PermissionError(13, "The process cannot access the file")

    monkeypatch.setattr(_model.os, "replace", locked)

    if existing:
        _model._publish(b"{}", output)  # noqa: SLF001
        assert output.read_text() == "{ }"
        assert sorted(output.parent.iterdir()) == [output]
    else:
        with pytest.raises(PermissionError):
            _model._publish(b"{}", output)  # noqa: SLF001
        assert list(output.parent.iterdir()) == []


@pytest.mark.parametrize(
    "dependency", [None, "https://example.com/latest.tar.gz"]
)
def test_registries_with_the_same_folder_name_keep_their_own_models(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    dependency: str | None,
) -> None:
    """Resolving one ``model`` registry leaves another's model in place."""

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        weaver_runs.append(command)
        registry = Path(command[command.index("--registry") + 1])
        spans = (registry / "spans.yaml").read_text()
        (Path(command[-1]) / "coverage-model.json").write_text(
            json.dumps({"spans": spans})
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model.subprocess, "run", run)
    registries = []
    for owner, groups in [("a", "[a]"), ("b", "[b]")]:
        if dependency is None:
            registry = _registry(tmp_path / owner / "model")
        else:
            registry = _depending_on(tmp_path / owner / "model", dependency)
        (registry / "spans.yaml").write_text(f"groups: {groups}\n")
        registries.append(registry)

    a = _model.coverage_model_for(registries[0])
    b = _model.coverage_model_for(registries[1])

    assert a != b
    assert _model.load(a) == {"spans": "groups: [a]\n"}
    assert _model.load(b) == {"spans": "groups: [b]\n"}
    assert _model.coverage_model_for(registries[0]) == a
    assert _model.load(a) == {"spans": "groups: [a]\n"}


def test_a_model_is_renamed_into_place(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parallel reader sees the whole model or none of it."""
    replaced: list[tuple[Path, Path]] = []
    replace = _model.os.replace

    def spy(source: str, target: Path) -> None:
        replaced.append((Path(source), Path(target)))
        replace(source, target)

    monkeypatch.setattr(_model.os, "replace", spy)
    output = _model.resolve(_registry(tmp_path / "model"), tmp_path / "m.json")

    assert [(s.parent, t) for s, t in replaced] == [(output.parent, output)]
    assert not list(output.parent.glob("*.tmp"))
    assert json.loads(output.read_text()) == {}


def _spans_weaver(
    monkeypatch: pytest.MonkeyPatch, runs: list[list[str]]
) -> None:
    """Weaver stubbed to put the registry's ``spans.yaml`` in its model."""

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        runs.append(command)
        registry = Path(command[command.index("--registry") + 1])
        (Path(command[-1]) / "coverage-model.json").write_text(
            json.dumps({"spans": (registry / "spans.yaml").read_text()})
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(_model.subprocess, "run", run)


def _stored(tmp_path: Path) -> list[Path]:
    """The working-tree models in the cache."""
    return sorted(
        (tmp_path / "cache" / "coverage-models" / "working-trees").iterdir()
    )


def _age(paths: list[Path]) -> None:
    """Make ``paths`` oldest first, all older than anything touched now."""
    start = time.time() - 1000
    for offset, path in enumerate(paths):
        os.utime(path, (start + offset, start + offset))


_KEPT = _model._KEPT_MODELS  # noqa: SLF001


def test_repeated_rebuilds_keep_a_bounded_cache_and_every_returned_model(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spans_weaver(monkeypatch, weaver_runs)
    registry = _registry(tmp_path / "model")
    returned: list[tuple[Path, str]] = []

    for edit in range(3 * _KEPT):
        spans = f"groups: [{edit}]\n"
        (registry / "spans.yaml").write_text(spans)
        returned.append((_model.coverage_model_for(registry), spans))
        assert len(_stored(tmp_path)) <= _KEPT

    assert len(weaver_runs) == 3 * _KEPT
    assert len(_stored(tmp_path)) == _KEPT
    assert len({path for path, _ in returned}) == 3 * _KEPT
    for path, spans in returned:
        assert _model.load(path) == {"spans": spans}


def test_the_most_recently_used_models_are_the_ones_kept(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    process: Callable[[], Path],
) -> None:
    _spans_weaver(monkeypatch, weaver_runs)
    registry = _registry(tmp_path / "model")
    oldest: list[Path] = []
    for edit in range(_KEPT):
        (registry / "spans.yaml").write_text(f"groups: [{edit}]\n")
        _model.coverage_model_for(registry)
        digest = _model._digest(registry)  # noqa: SLF001
        (built,) = [p for p in _stored(tmp_path) if f"-{digest}-" in p.name]
        oldest.append(built)
    _age(oldest)
    (registry / "spans.yaml").write_text("groups: [0]\n")

    process()
    reused = _model.coverage_model_for(registry)
    (registry / "spans.yaml").write_text("groups: [new]\n")
    _model.coverage_model_for(registry)

    assert len(weaver_runs) == _KEPT + 1
    assert _model.load(reused) == {"spans": "groups: [0]\n"}
    assert oldest[0] in _stored(tmp_path)
    assert oldest[1] not in _stored(tmp_path)


def test_a_model_pruned_by_another_run_stays_with_whoever_it_was_returned_to(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    process: Callable[[], Path],
) -> None:
    """Two runs, two registries both named ``model``, one shared cache."""
    _spans_weaver(monkeypatch, weaver_runs)
    a = _registry(tmp_path / "a" / "model")
    (a / "spans.yaml").write_text("groups: [a]\n")
    b = _registry(tmp_path / "b" / "model")

    first = _model.coverage_model_for(a)
    (stored,) = _stored(tmp_path)
    _age([stored])
    process()
    for edit in range(_KEPT):
        (b / "spans.yaml").write_text(f"groups: [b{edit}]\n")
        _model.coverage_model_for(b)
    assert stored not in _stored(tmp_path)
    process()
    again = _model.coverage_model_for(a)

    assert _model.load(first) == {"spans": "groups: [a]\n"}
    assert _model.load(again) == {"spans": "groups: [a]\n"}
    assert again != first
    assert len(weaver_runs) == _KEPT + 2


def test_a_model_windows_reports_as_being_removed_is_resolved_again(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    process: Callable[[], Path],
) -> None:
    """Opening a file pending deletion fails rather than reading it."""
    _spans_weaver(monkeypatch, weaver_runs)
    registry = _registry(tmp_path / "model")
    _model.coverage_model_for(registry)
    (stored,) = _stored(tmp_path)
    read_bytes = Path.read_bytes

    def pending(path: Path) -> bytes:
        if path == stored:
            raise PermissionError(13, "Access is denied")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", pending)
    process()
    model = _model.coverage_model_for(registry)

    assert len(weaver_runs) == 2
    assert _model.load(model) == {"spans": "groups: []\n"}


def test_a_model_windows_will_not_remove_or_touch_is_left_for_later(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    process: Callable[[], Path],
) -> None:
    """Another run has it open, so removing it fails; nothing else does."""
    _spans_weaver(monkeypatch, weaver_runs)
    registry = _registry(tmp_path / "model")
    first = _model.coverage_model_for(registry)
    (locked,) = _stored(tmp_path)
    _age([locked])
    unlink = Path.unlink

    def in_use(path: Path, missing_ok: bool = False) -> None:  # noqa: FBT001, FBT002
        if path == locked:
            raise PermissionError(32, "The file is in use")
        unlink(path, missing_ok=missing_ok)

    def no_touch(*_args: object, **_kwargs: object) -> None:
        raise PermissionError(32, "The file is in use")

    monkeypatch.setattr(Path, "unlink", in_use)
    monkeypatch.setattr(_model.os, "utime", no_touch)
    for edit in range(_KEPT):
        (registry / "spans.yaml").write_text(f"groups: [{edit}]\n")
        _model.coverage_model_for(registry)
    process()
    (registry / "spans.yaml").write_text("groups: []\n")
    reused = _model.coverage_model_for(registry)

    assert locked in _stored(tmp_path)
    assert len(weaver_runs) == _KEPT + 1
    assert _model.load(first) == _model.load(reused)
    assert not list(locked.parent.glob(".*.tmp"))


def _pinned(tmp_path: Path) -> list[Path]:
    """The pinned models in the cache."""
    return sorted(
        (tmp_path / "cache" / "coverage-models" / "pinned").iterdir()
    )


def _pin(checkout: Path, pin: str) -> Path:
    """The model for ``checkout`` pinned as ``pin``."""
    return _model.coverage_model_for(checkout, pin=pin)


def test_pinned_models_keep_a_bounded_cache_and_every_returned_model(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spans_weaver(monkeypatch, weaver_runs)
    checkout = _registry(tmp_path / "checkout" / "model")
    returned: list[tuple[Path, str]] = []

    for ref in range(3 * _KEPT):
        spans = f"groups: [{ref}]\n"
        (checkout / "spans.yaml").write_text(spans)
        returned.append((_pin(checkout, f"semconv-v{ref}-model"), spans))
        assert len(_pinned(tmp_path)) <= _KEPT

    assert len(weaver_runs) == 3 * _KEPT
    assert len(_pinned(tmp_path)) == _KEPT
    assert len({path for path, _ in returned}) == 3 * _KEPT
    for path, spans in returned:
        assert _model.load(path) == {"spans": spans}


def test_a_pinned_model_is_reused_by_this_run_and_the_next(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    process: Callable[[], Path],
) -> None:
    _spans_weaver(monkeypatch, weaver_runs)
    checkout = _registry(tmp_path / "checkout" / "model")
    first = _pin(checkout, "semconv-v1-model")
    assert _pin(checkout, "semconv-v1-model") == first

    process()
    again = _pin(checkout, "semconv-v1-model")

    assert again != first
    assert (
        _model.load(again) == _model.load(first) == {"spans": "groups: []\n"}
    )
    assert len(weaver_runs) == 1


def test_the_most_recently_used_pinned_models_are_the_ones_kept(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    process: Callable[[], Path],
) -> None:
    _spans_weaver(monkeypatch, weaver_runs)
    checkout = _registry(tmp_path / "checkout" / "model")
    for ref in range(_KEPT):
        _pin(checkout, f"semconv-v{ref}-model")
    oldest = [
        tmp_path / "cache" / "coverage-models" / "pinned" / name
        for ref in range(_KEPT)
        for name in [f"semconv-v{ref}-model-{_model.fingerprint()}.json"]
    ]
    assert _pinned(tmp_path) == sorted(oldest)
    _age(oldest)

    process()
    _pin(checkout, "semconv-v0-model")
    _pin(checkout, "semconv-new-model")

    assert len(weaver_runs) == _KEPT + 1
    assert oldest[0] in _pinned(tmp_path)
    assert oldest[1] not in _pinned(tmp_path)


def test_a_pruned_pinned_model_stays_with_whoever_it_was_returned_to(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
    process: Callable[[], Path],
) -> None:
    _spans_weaver(monkeypatch, weaver_runs)
    checkout = _registry(tmp_path / "checkout" / "model")
    (checkout / "spans.yaml").write_text("groups: [v1]\n")
    first = _pin(checkout, "semconv-v1-model")
    (stored,) = _pinned(tmp_path)
    _age([stored])

    process()
    for ref in range(_KEPT):
        _pin(checkout, f"semconv-other{ref}-model")
    assert stored not in _pinned(tmp_path)
    assert _model.load(first) == {"spans": "groups: [v1]\n"}

    process()
    again = _pin(checkout, "semconv-v1-model")
    assert _model.load(again) == {"spans": "groups: [v1]\n"}
    assert len(weaver_runs) == _KEPT + 2


def test_a_pin_with_a_separator_is_pruned_with_the_others(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spans_weaver(monkeypatch, weaver_runs)
    checkout = _registry(tmp_path / "checkout" / "model")
    (checkout / "spans.yaml").write_text("groups: [branch]\n")
    branch = _pin(checkout, "semconv-release/v1-model")
    (checkout / "spans.yaml").write_text("groups: [dashed]\n")
    dashed = _pin(checkout, "semconv-release-v1-model")

    assert all(path.is_file() for path in _pinned(tmp_path))
    assert len(_pinned(tmp_path)) == 2
    assert _model.load(branch) == {"spans": "groups: [branch]\n"}
    assert _model.load(dashed) == {"spans": "groups: [dashed]\n"}

    _age(_pinned(tmp_path))
    for ref in range(_KEPT):
        _pin(checkout, f"semconv-v{ref}-model")
    assert len(_pinned(tmp_path)) == _KEPT
    assert not any("release" in path.name for path in _pinned(tmp_path))


def test_pruning_one_kind_of_model_leaves_the_rest_of_the_cache(
    tmp_path: Path,
    weaver_runs: list[list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Earlier pinned models, other files and the other kind are kept."""
    _spans_weaver(monkeypatch, weaver_runs)
    models = tmp_path / "cache" / "coverage-models"
    models.mkdir(parents=True)
    earlier = models / "semconv-v0-model-0123456789ab.json"
    earlier.write_text("{}")
    unrelated = models / "notes.json"
    unrelated.write_text("{}")
    registry = _registry(tmp_path / "model")
    _model.coverage_model_for(registry)
    (working,) = _stored(tmp_path)
    checkout = _registry(tmp_path / "checkout" / "model")
    _pin(checkout, "semconv-v1-model")
    (pinned,) = _pinned(tmp_path)
    _age([earlier, unrelated, working, pinned])

    for edit in range(2 * _KEPT):
        _pin(checkout, f"semconv-other{edit}-model")
        (registry / "spans.yaml").write_text(f"groups: [{edit}]\n")
        _model.coverage_model_for(registry)

    assert working not in _stored(tmp_path)
    assert pinned not in _pinned(tmp_path)
    assert len(_stored(tmp_path)) == len(_pinned(tmp_path)) == _KEPT
    assert earlier.read_text() == unrelated.read_text() == "{}"
    assert sorted(models.glob("*.json")) == [unrelated, earlier]


def test_a_processs_models_are_removed_when_it_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    at_exit: list[Callable[[], object]] = []

    def register(
        function: Callable[..., object], *args: object, **kwargs: object
    ) -> None:
        at_exit.append(lambda: function(*args, **kwargs))

    monkeypatch.setattr(_model.atexit, "register", register)
    monkeypatch.setattr(_model.tempfile, "tempdir", str(tmp_path))
    directory = _PROCESS_MODELS.__wrapped__()
    assert directory.parent == tmp_path
    (directory / "model.json").write_text("{}")

    (cleanup,) = at_exit
    cleanup()

    assert not directory.exists()


@pytest.mark.skipif(
    shutil.which("weaver") is None, reason="weaver not installed"
)
def test_resolved_model_keeps_span_and_metric_refinements(tmp_path):
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "manifest.yaml").write_text(
        "name: demo\nschema_url: https://example.com/schemas/1.0.0\n"
    )
    (registry / "signals.yaml").write_text(
        """\
file_format: definition/2
attributes:
  - key: demo.name
    type: string
    brief: The tool name.
    stability: development
  - key: demo.skill
    type: string
    brief: The skill name.
    stability: development
spans:
  - type: demo.tool
    name:
      note: Tool execution.
    kind: internal
    brief: Tool execution.
    stability: development
    requirement_level: recommended
    attributes:
      - ref: demo.name
        requirement_level: required
span_refinements:
  - id: demo.tool.skill
    ref: demo.tool
    brief: Skill execution.
    stability: development
    attributes:
      - ref: demo.skill
        requirement_level: required
metrics:
  - name: demo.duration
    instrument: histogram
    unit: s
    brief: Tool duration.
    stability: development
    requirement_level: recommended
    attributes:
      - ref: demo.name
        requirement_level: required
metric_refinements:
  - id: demo.skill.duration
    ref: demo.duration
    brief: Skill duration.
    stability: development
    attributes:
      - ref: demo.skill
        requirement_level: recommended
"""
    )
    output = _model.resolve(registry, tmp_path / "model.json")
    model = _model.load(output)

    for kind, base, refinement in [
        ("spans", "demo.tool", "demo.tool.skill"),
        ("metrics", "demo.duration", "demo.skill.duration"),
    ]:
        assert "demo.skill" not in model[kind][base]["attributes"]
        assert (
            "demo.skill"
            in model[kind][base]["refinements"][refinement]["attributes"]
        )
    assert "demo.skill" in model["spans"]["demo.tool.skill"]["attributes"]
    assert list(model["metrics"]) == ["demo.duration"]


@pytest.mark.skipif(
    shutil.which("weaver") is None, reason="weaver not installed"
)
def test_a_weaver_toml_above_the_working_directory_leaves_the_model_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "manifest.yaml").write_text(
        "name: demo\nschema_url: https://example.com/schemas/1.0.0\n"
    )
    shared = tmp_path / "shared"
    shared.mkdir()
    for folder, name in [(registry, "demo.tool"), (shared, "demo.shared")]:
        (folder / "signals.yaml").write_text(
            f"""\
file_format: definition/2
attributes:
  - key: {name}.name
    type: string
    brief: A name.
    stability: development
spans:
  - type: {name}
    name:
      note: A span.
    kind: internal
    brief: A span.
    stability: development
    attributes:
      - ref: {name}.name
"""
        )
    try:
        (registry / "shared").symlink_to(shared, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available here")
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.chdir(plain)
    expected = _model.load(_model.resolve(registry, tmp_path / "plain.json"))

    project = tmp_path / "project"
    (project / "nested").mkdir(parents=True)
    (project / ".weaver.toml").write_text(
        "[registry]\nfollow_symlinks = true\ninclude_unreferenced = true\n"
    )
    monkeypatch.chdir(project / "nested")
    model = _model.load(_model.resolve(registry, tmp_path / "project.json"))

    assert list(expected["spans"]) == ["demo.tool"]
    assert model == expected
