#!/usr/bin/env python3
"""Validate and apply generated data patches from an untrusted workflow run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath

_CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_FORBIDDEN_METADATA = (
    b"old mode ",
    b"new mode ",
    b"new file mode ",
    b"deleted file mode ",
    b"similarity index ",
    b"rename from ",
    b"rename to ",
    b"copy from ",
    b"copy to ",
    b"GIT binary patch",
)


class PatchError(RuntimeError):
    """A patch is malformed, unsafe, or does not apply to the target."""


def _run_git(repository: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        capture_output=True,
        creationflags=_CREATE_NO_WINDOW,
        stdin=subprocess.DEVNULL,
    )


def _git_output(repository: Path, *args: str) -> bytes:
    try:
        return _run_git(repository, *args).stdout
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.decode("utf-8", errors="replace").strip()
        raise PatchError(stderr or f"git {' '.join(args)} failed") from error


def _patch_files(sources: Iterable[Path]) -> list[Path]:
    patches: list[Path] = []
    for source in sources:
        if source.is_file() and source.suffix == ".patch":
            patches.append(source)
        elif source.is_dir():
            patches.extend(source.rglob("*.patch"))
        elif source.exists():
            raise PatchError(f"patch source is not a file or directory: {source}")
    return sorted(set(patches))


def _validated_path(repository: Path, raw_path: bytes) -> str:
    try:
        path = raw_path.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PatchError("patch path is not UTF-8") from error

    pure_path = PurePosixPath(path)
    parts = pure_path.parts
    if (
        "\\" in path
        or pure_path.is_absolute()
        or len(parts) < 3
        or parts[0] != "scenarios"
        or parts[-1] != "data.json"
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise PatchError(f"patch modifies disallowed path: {path}")

    candidate = repository.joinpath(*parts)
    repository_root = repository.resolve(strict=True)
    try:
        candidate.resolve(strict=True).relative_to(repository_root)
    except (FileNotFoundError, ValueError) as error:
        raise PatchError(f"patch target is not an existing repository file: {path}") from error

    current = repository
    for part in parts:
        current /= part
        if current.is_symlink():
            raise PatchError(f"patch target traverses a symbolic link: {path}")
    if not candidate.is_file():
        raise PatchError(f"patch target is not a regular file: {path}")
    return path


def _inspect_patch(repository: Path, patch: Path) -> tuple[str, ...]:
    contents = patch.read_bytes()
    if not contents:
        raise PatchError(f"patch is empty: {patch}")
    for line in contents.splitlines():
        if line.startswith(_FORBIDDEN_METADATA):
            raise PatchError(f"patch contains unsupported metadata in {patch}: {line!r}")

    output = _git_output(
        repository,
        "apply",
        "--numstat",
        "-z",
        "--",
        str(patch.resolve()),
    )
    records = output.split(b"\0")
    if not records or records[-1] != b"":
        raise PatchError(f"git returned malformed numstat output for {patch}")

    paths: list[str] = []
    for record in records[:-1]:
        fields = record.split(b"\t", 2)
        if (
            len(fields) != 3
            or not fields[0].isdigit()
            or not fields[1].isdigit()
            or not fields[2]
        ):
            raise PatchError(f"patch contains an unsupported change: {patch}")
        paths.append(_validated_path(repository, fields[2]))
    if not paths:
        raise PatchError(f"patch does not modify any files: {patch}")
    if len(paths) != len(set(paths)):
        raise PatchError(f"patch modifies the same file more than once: {patch}")
    return tuple(paths)


def apply_patches(repository: Path, sources: Sequence[Path]) -> tuple[str, ...]:
    """Validate all discovered patches, apply them, and return changed paths."""
    repository = repository.resolve(strict=True)
    patches = _patch_files(sources)
    if not patches:
        return ()

    patch_paths: list[tuple[Path, tuple[str, ...]]] = []
    expected_paths: set[str] = set()
    for patch in patches:
        paths = _inspect_patch(repository, patch)
        duplicates = expected_paths.intersection(paths)
        if duplicates:
            duplicate_list = ", ".join(sorted(duplicates))
            raise PatchError(f"multiple patches modify the same file: {duplicate_list}")
        expected_paths.update(paths)
        patch_paths.append((patch, paths))

    for patch, _ in patch_paths:
        resolved_patch = str(patch.resolve())
        _git_output(repository, "apply", "--check", "--whitespace=nowarn", "--", resolved_patch)
        _git_output(repository, "apply", "--whitespace=nowarn", "--", resolved_patch)

    changed_output = _git_output(repository, "diff", "--name-only", "-z", "--")
    changed_paths = {
        path.decode("utf-8")
        for path in changed_output.split(b"\0")
        if path
    }
    if changed_paths != expected_paths:
        raise PatchError(
            "applied paths do not match validated paths: "
            f"expected {sorted(expected_paths)}, found {sorted(changed_paths)}"
        )

    for path in sorted(changed_paths):
        candidate = repository.joinpath(*PurePosixPath(path).parts)
        if candidate.is_symlink() or not candidate.is_file():
            raise PatchError(f"applied patch changed the file type: {path}")
        try:
            with candidate.open(encoding="utf-8") as data_file:
                json.load(data_file)
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise PatchError(f"applied patch produced invalid JSON: {path}") from error

    return tuple(sorted(changed_paths))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("sources", nargs="+", type=Path)
    args = parser.parse_args()

    try:
        changed_paths = apply_patches(args.repository, args.sources)
    except PatchError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if changed_paths:
        print("Applied generated data changes:")
        for path in changed_paths:
            print(f"- {path}")
    else:
        print("No generated data patches found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
