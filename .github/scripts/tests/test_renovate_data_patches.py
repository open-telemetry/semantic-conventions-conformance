from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_script() -> ModuleType:
    script_path = Path(__file__).parents[1] / "renovate_data_patches.py"
    spec = importlib.util.spec_from_file_location("renovate_data_patches", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


patches = _load_script()

DATA_PATH = Path("scenarios/http/python/example/data.json")


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    patches._run_git(tmp_path, "init")
    patches._run_git(tmp_path, "config", "user.name", "Test")
    patches._run_git(tmp_path, "config", "user.email", "test@example.com")
    data_file = tmp_path / DATA_PATH
    data_file.parent.mkdir(parents=True)
    data_file.write_text('{"value": 1}\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("original\n", encoding="utf-8")
    patches._run_git(tmp_path, "add", ".")
    patches._run_git(tmp_path, "commit", "-m", "Initial")
    return tmp_path


def _create_patch(repository: Path, path: Path, content: str, destination: Path) -> Path:
    target = repository / path
    original = target.read_text(encoding="utf-8") if target.exists() else None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    if original is None:
        patches._run_git(repository, "add", "--intent-to-add", "--", path.as_posix())
    destination.write_bytes(
        patches._run_git(repository, "diff", "--binary", "--", path.as_posix()).stdout
    )
    if original is None:
        patches._run_git(repository, "reset", "--", path.as_posix())
        target.unlink()
    else:
        target.write_text(original, encoding="utf-8")
    return destination


def test_applies_existing_data_json_patch(repository: Path, tmp_path: Path) -> None:
    patch = _create_patch(repository, DATA_PATH, '{"value": 2}\n', tmp_path / "valid.patch")

    changed = patches.apply_patches(repository, [patch])

    assert changed == (DATA_PATH.as_posix(),)
    assert (repository / DATA_PATH).read_text(encoding="utf-8") == '{"value": 2}\n'


def test_missing_patch_directory_is_noop(repository: Path, tmp_path: Path) -> None:
    assert patches.apply_patches(repository, [tmp_path / "missing"]) == ()


def test_rejects_path_outside_generated_data(repository: Path, tmp_path: Path) -> None:
    patch = _create_patch(repository, Path("README.md"), "changed\n", tmp_path / "readme.patch")

    with pytest.raises(patches.PatchError, match="disallowed path"):
        patches.apply_patches(repository, [patch])


def test_rejects_new_data_file(repository: Path, tmp_path: Path) -> None:
    new_path = Path("scenarios/http/python/new/data.json")
    patch = _create_patch(repository, new_path, "{}\n", tmp_path / "new.patch")

    with pytest.raises(patches.PatchError, match="unsupported metadata"):
        patches.apply_patches(repository, [patch])


def test_rejects_duplicate_targets(repository: Path, tmp_path: Path) -> None:
    first = _create_patch(repository, DATA_PATH, '{"value": 2}\n', tmp_path / "first.patch")
    second = _create_patch(repository, DATA_PATH, '{"value": 3}\n', tmp_path / "second.patch")

    with pytest.raises(patches.PatchError, match="multiple patches"):
        patches.apply_patches(repository, [first, second])


def test_rejects_duplicate_target_within_patch(repository: Path, tmp_path: Path) -> None:
    first = _create_patch(repository, DATA_PATH, '{"value": 2}\n', tmp_path / "first.patch")
    second = _create_patch(repository, DATA_PATH, '{"value": 3}\n', tmp_path / "second.patch")
    combined = tmp_path / "combined.patch"
    combined.write_bytes(first.read_bytes() + second.read_bytes())

    with pytest.raises(patches.PatchError, match="same file more than once"):
        patches.apply_patches(repository, [combined])


def test_rejects_malformed_patch(repository: Path, tmp_path: Path) -> None:
    patch = tmp_path / "malformed.patch"
    patch.write_text("not a patch\n", encoding="utf-8")

    with pytest.raises(patches.PatchError, match="No valid patches"):
        patches.apply_patches(repository, [patch])


def test_rejects_patch_for_stale_file(repository: Path, tmp_path: Path) -> None:
    patch = _create_patch(repository, DATA_PATH, '{"value": 2}\n', tmp_path / "stale.patch")
    (repository / DATA_PATH).write_text('{"value": 3}\n', encoding="utf-8")
    patches._run_git(repository, "add", DATA_PATH.as_posix())
    patches._run_git(repository, "commit", "-m", "Advance")

    with pytest.raises(patches.PatchError, match="patch failed"):
        patches.apply_patches(repository, [patch])


def test_rejects_invalid_json(repository: Path, tmp_path: Path) -> None:
    patch = _create_patch(repository, DATA_PATH, "{\n", tmp_path / "invalid-json.patch")

    with pytest.raises(patches.PatchError, match="invalid JSON"):
        patches.apply_patches(repository, [patch])
