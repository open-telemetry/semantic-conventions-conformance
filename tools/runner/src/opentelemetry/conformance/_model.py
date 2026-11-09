# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The coverage model: what a registry declares, per signal and entity.

Weaver resolves a registry into one JSON file. Span refinements keep their own
ids, so a classifier can select a provider-specific definition without
counting its attributes as coverage of the base signal. Base spans and metrics
also list their refinements, so a reduction can keep the fields those declare
without inferring which refinement applies. Metrics are keyed by name only::

    {"spans":    {"http.server": {"kind": "server", "attributes": {name: level},
                                  "refinements": {id: {"attributes": {name: level}}}}},
     "events":   {name: {"attributes": {name: level}}},
     "metrics":  {name: {"attributes": {name: level},
                         "refinements": {id: {"attributes": {name: level}}}}},
     "entities": {name: {"identity": {name: level}, "description": {name: level}}}}

That is what a reduction reads to say which of a signal's declared attributes
a run actually carried.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager, suppress
from functools import cache
from pathlib import Path
from typing import Any, cast

import yaml

from ._registry import cache_dir, check_weaver, weaver_version

logger = logging.getLogger(__name__)

_TEMPLATES = Path(__file__).parent / "weaver-templates"

# What weaver reads from a registry directory: YAML files, skipping anything
# whose name starts with a dot.
_DEFINITIONS = (".yaml", ".yml")
_MANIFESTS = ("manifest.yaml", "registry_manifest.yaml")

# Weaver's ``source[@refspec][[sub_folder]]`` form of a registry path.
_REGISTRY_PATH = re.compile(
    r"^(?P<source>.+?)(?:@(?P<refspec>.+?))?(?:\[(?P<sub_folder>.+?)])?$"
)
# How many models each of the cache's pinned and working-tree directories
# keeps, most recently used first.
_KEPT_MODELS = 8


@cache
def fingerprint() -> str:
    """A digest of what turns a registry into a model.

    Part of a cached model's name, so editing the template or the weaver call
    below asks for a fresh model instead of reading back the old shape.
    """
    digest = hashlib.sha256()
    for path in sorted(_TEMPLATES.rglob("*")):
        if path.is_file():
            digest.update(path.read_bytes())
    digest.update(weaver_version().encode())
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()[:12]


def coverage_model_for(registry: Path, *, pin: str | None = None) -> Path:
    """The coverage model for ``registry``, resolved once into the cache.

    A pinned registry is cached under its pin. Any other is somebody's
    working tree. One whose dependencies are all local registry directories
    is cached under a digest of the files weaver reads, its own and theirs:
    an edit, a delete or a rename asks for a fresh model, and a repeat run
    over the same files reuses the last one. The cache keeps only the
    ``_KEPT_MODELS`` most recently used pinned models, and as many working
    tree ones, so the caller gets its own copy, which nothing removes until
    this process exits. One that depends on anything fetched by URL or on an
    archive is resolved again on every call, since that can depend on
    something that moves, and only that copy is written.
    """
    models = cache_dir() / "coverage-models"
    if pin is not None:
        return _cached(
            registry, models / "pinned", f"{_flat(pin)}-{fingerprint()}"
        )

    name = registry.resolve().name or "registry"
    digest = _digest(registry)
    if digest is None:
        with _generated(registry) as produced:
            model = produced.read_bytes()
        content = hashlib.sha256(model).hexdigest()[:16]
        output = (
            _process_models()
            / f"{name}-unpinned-{content}-{fingerprint()}.json"
        )
        _publish(model, output)
        return output

    return _cached(
        registry, models / "working-trees", f"{name}-{digest}-{fingerprint()}"
    )


def _cached(registry: Path, directory: Path, key: str) -> Path:
    """This process's copy of the model for ``registry`` stored as ``key``.

    ``directory`` holds only models the runner stored there, so pruning it
    to the ``_KEPT_MODELS`` most recently used removes nothing else.
    """
    output = _process_models() / directory.name / f"{key}.json"
    if output.is_file():
        return output
    stored = directory / f"{key}.json"
    try:
        model = stored.read_bytes()
    except OSError:
        # Not resolved yet, or removed by another run's prune, or being
        # removed, which Windows reports as a permission error.
        logger.info("Resolving the coverage model into %s", stored)
        with _generated(registry) as produced:
            model = produced.read_bytes()
        _publish(model, stored)
    else:
        with suppress(OSError):
            os.utime(stored)
    _publish(model, output)
    _prune(directory, keep=stored)
    return output


def _flat(pin: str) -> str:
    """``pin`` as one file name, so a ref like ``release/v1`` stays pruned.

    A pin that had a separator also gets a digest of itself, so it can't
    share a name with one that already had a dash there instead.
    """
    flat = pin.replace("/", "-").replace("\\", "-")
    if flat == pin:
        return pin
    return f"{flat}-{hashlib.sha256(pin.encode()).hexdigest()[:8]}"


@cache
def _process_models() -> Path:
    """Where this process keeps the models it returns, until it exits."""
    directory = Path(tempfile.mkdtemp(prefix="otel-conformance-models-"))
    atexit.register(shutil.rmtree, directory, ignore_errors=True)
    return directory


def _prune(directory: Path, *, keep: Path) -> None:
    """Remove all but the ``_KEPT_MODELS`` newest models in ``directory``.

    Every caller holds its own copy, so a removed model only costs a later
    run a rebuild. One another run is reading, which Windows won't remove,
    stays until a later prune.
    """
    found: list[tuple[float, Path]] = []
    for path in directory.glob("*.json"):
        with suppress(OSError):
            found.append((path.stat().st_mtime, path))
    found.sort(reverse=True)
    others = [path for _, path in found if path != keep]
    for path in others[_KEPT_MODELS - 1 :]:
        with suppress(OSError):
            path.unlink()


def _digest(registry: Path) -> str | None:
    """A digest of what weaver reads for ``registry``.

    ``None`` when a dependency can change without any file here changing.
    """
    root = registry.resolve()
    cache = cache_dir().resolve()
    if cache == root:
        raise RuntimeError(
            f"SEMCONV_CACHE is the registry {registry} itself. The runner "
            "writes generated files there, so point it at another directory."
        )
    digest = hashlib.sha256()
    if not _feed(digest, root, cache=cache, seen=set()):
        return None
    return digest.hexdigest()[:12]


def _feed(digest: Any, root: Path, *, cache: Path, seen: set[Path]) -> bool:
    """Feed ``root``'s definitions and its dependencies' into ``digest``.

    False when a dependency can change without a file here changing.
    """
    if root in seen:
        return True
    seen.add(root)
    digest.update(b"registry\0")
    for relative, path in _definitions(root, cache):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    for dependency in _dependencies(root):
        registry_path = dependency.get("registry_path")
        if registry_path is None:
            # Weaver fetches the schema URL, whose content can change.
            return False
        registry_path = str(registry_path)
        match = _REGISTRY_PATH.match(registry_path)
        if match is None:
            return False
        source = match["source"]
        if source.startswith(("http://", "https://")):
            # Even a git commit can depend on a branch, a tag or an archive
            # that moves, and weaver resolves dependencies recursively.
            return False
        if source.endswith((".zip", ".tar.gz")):
            # An archive's own manifest can depend on something that moves.
            return False
        # Weaver reads a local folder whole: it keeps only ``source`` and
        # ignores any ``@refspec`` or ``[sub_folder]`` that follows it.
        local = _local(source, root)
        if local is None:
            return False
        digest.update(f"dependency\0{local}\0{registry_path}\0".encode())
        if not _feed(digest, local, cache=cache, seen=seen):
            return False
    return True


def _definitions(root: Path, cache: Path) -> list[tuple[str, Path]]:
    """The YAML files weaver reads under ``root``, by their path within it.

    Symlinked folders are followed, once each, and a cache inside ``root`` is
    left out, since the runner generates files there.
    """
    found: list[tuple[str, Path]] = []
    visited: set[str] = set()
    for directory, folders, files in os.walk(root, followlinks=True):
        real = os.path.realpath(directory)
        if real in visited or Path(real) == cache:
            folders[:] = []
            continue
        visited.add(real)
        folders[:] = [f for f in folders if not f.startswith(".")]
        relative = Path(directory).relative_to(root)
        for file in files:
            if not file.startswith(".") and file.endswith(_DEFINITIONS):
                found.append(
                    ((relative / file).as_posix(), Path(directory, file))
                )
    return sorted(found)


def _dependencies(root: Path) -> list[dict[str, Any]]:
    """The dependencies ``root``'s manifest declares."""
    for name in _MANIFESTS:
        manifest = root / name
        if manifest.is_file():
            loaded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                return []
            declared = cast("dict[str, object]", loaded).get("dependencies")
            if not isinstance(declared, list):
                return []
            return [
                cast("dict[str, Any]", entry)
                for entry in cast("list[object]", declared)
                if isinstance(entry, dict)
            ]
    return []


def _local(source: str, root: Path) -> Path | None:
    """Where a local dependency is, or ``None`` if it can't be found.

    Weaver reads a relative path from its working directory, so that is
    looked at first, then the registry's own directory.
    """
    path = Path(source)
    candidates = (
        [path] if path.is_absolute() else [Path.cwd() / path, root / path]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return None


def resolve(registry: Path, output: Path) -> Path:
    """Resolve ``registry`` into a coverage model at ``output``, once.

    ``output`` is expected to name what it was resolved from, so a new pin or
    an edited registry asks for a fresh model rather than silently reusing the
    old one.
    """
    if output.is_file():
        return output

    logger.info("Resolving the coverage model into %s", output)
    with _generated(registry) as produced:
        _publish(produced.read_bytes(), output)
    return output


@contextmanager
def _generated(registry: Path) -> Generator[Path, None, None]:
    """Run weaver over ``registry``; the model it wrote, while it exists."""
    check_weaver()

    with tempfile.TemporaryDirectory() as generated:
        completed = subprocess.run(  # noqa: S603
            [
                "weaver",
                "registry",
                "generate",
                "--quiet",
                "--v2",
                "--registry",
                str(registry),
                "--templates",
                str(_TEMPLATES),
                "coverage-model",
                generated,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        produced = Path(generated) / "coverage-model.json"
        if completed.returncode != 0 or not produced.is_file():
            raise RuntimeError(
                f"Could not resolve the coverage model for {registry}: "
                f"{completed.stderr.strip() or completed.stdout.strip()}"
            )
        yield produced


def _publish(model: bytes, output: Path) -> None:
    """Put ``model`` at ``output`` so that no reader sees half of it.

    The temp directory is often another filesystem from the cache, so the
    model is written next to ``output`` first and then renamed over it. Every
    ``output`` is named after what its model was resolved from, so one already
    there is the same model: it is left alone, including when Windows won't
    replace it because another run has it open.
    """
    if _holds(output, model):
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, staged = tempfile.mkstemp(
        dir=output.parent, prefix=f".{output.stem}-", suffix=".tmp"
    )
    os.close(handle)
    try:
        Path(staged).write_bytes(model)
        try:
            os.replace(staged, output)
        except PermissionError:
            if not output.is_file():
                raise
    finally:
        Path(staged).unlink(missing_ok=True)


def _holds(path: Path, model: bytes) -> bool:
    """Whether ``path`` is a file holding exactly ``model``."""
    try:
        return path.read_bytes() == model
    except OSError:
        return False


def load(path: Path) -> dict[str, dict[str, Any]]:
    """Read a resolved coverage model."""
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found — resolve the registry into a coverage model "
            "before reducing a run."
        )
    return json.loads(path.read_text(encoding="utf-8"))
