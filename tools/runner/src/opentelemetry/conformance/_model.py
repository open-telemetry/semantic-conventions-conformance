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
# A published registry's manifest, which points at a resolved registry that
# can be anywhere, instead of at definitions next to it.
_PUBLISHED = "manifest/2.0"

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
    this process exits. One that depends on anything fetched by URL, on an
    archive or on a published registry is resolved again on every call,
    since that can depend on something that moves, and only that copy is
    written. So is any registry, pinned or not, while the ``.weaver.toml``
    weaver reads can send a schema URL somewhere else.
    """
    models = cache_dir() / "coverage-models"
    overridden = _overrides_schema_urls()
    if pin is not None:
        if overridden:
            return _uncached(registry, _flat(pin))
        return _cached(
            registry, models / "pinned", f"{_flat(pin)}-{fingerprint()}"
        )

    name = registry.resolve().name or "registry"
    digest = None if overridden else _digest(registry)
    if digest is None:
        return _uncached(registry, f"{name}-unpinned")

    return _cached(
        registry, models / "working-trees", f"{name}-{digest}-{fingerprint()}"
    )


def _uncached(registry: Path, name: str) -> Path:
    """This process's copy of a model for ``registry``, resolved now."""
    with _generated(registry) as produced:
        model = produced.read_bytes()
    content = hashlib.sha256(model).hexdigest()[:16]
    output = _process_models() / f"{name}-{content}-{fingerprint()}.json"
    _publish(model, output)
    return output


def _overrides_schema_urls() -> bool:
    """Whether the ``.weaver.toml`` weaver reads may override schema URLs.

    Weaver reads the first one in or above the working directory. Its
    ``[resolve.schema_url_overrides]`` can send a dependency to another
    folder or URL, which no digest here follows. Only the key's name is
    looked for, so one in a comment just costs the cache.
    """
    cwd = Path.cwd()
    for directory in (cwd, *cwd.parents):
        config = directory / ".weaver.toml"
        if config.is_file():
            try:
                text = config.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                return True
            return "schema_url_overrides" in text
    return False


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
    if not root.is_dir():
        # A manifest file, maybe a published one.
        return None
    dependencies = _local_dependencies(root)
    if dependencies is None:
        return None
    digest = hashlib.sha256()
    _feed(digest, root, cache)
    for dependency in dependencies:
        digest.update(f"dependency\0{dependency}\0".encode())
        _feed(digest, dependency, cache)
    return digest.hexdigest()[:12]


def _feed(digest: Any, registry: Path, cache: Path) -> None:
    """Feed the definitions weaver reads in ``registry`` into ``digest``."""
    digest.update(b"registry\0")
    for relative, path in _definitions(registry, cache):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())


def _local_dependencies(root: Path) -> list[Path] | None:
    """The registries ``root`` depends on, directly or not, each once.

    ``None`` when one can change without any file here changing, including
    when one is published. Only manifests are read for this, so a registry
    that can't be cached costs no more than that.
    """
    found: list[Path] = []
    pending = [root]
    while pending:
        registry = pending.pop()
        dependencies = _dependencies(registry)
        if dependencies is None:
            return None
        for dependency in dependencies:
            local = _local_dependency(dependency, registry)
            if local is None:
                return None
            if local != root and local not in found:
                found.append(local)
                pending.append(local)
    return found


def _local_dependency(dependency: dict[str, Any], root: Path) -> Path | None:
    """The local folder weaver reads for ``dependency`` of ``root``.

    ``None`` when it is anything else, or can't be found.
    """
    registry_path = dependency.get("registry_path")
    if registry_path is None:
        # Weaver fetches the schema URL, whose content can change.
        return None
    match = _REGISTRY_PATH.match(str(registry_path))
    if match is None:
        return None
    source = match["source"]
    if source.startswith(("http://", "https://")):
        # Even a git commit can depend on a branch, a tag or an archive
        # that moves, and weaver resolves dependencies recursively.
        return None
    if source.endswith((".zip", ".tar.gz")):
        # An archive's own manifest can depend on something that moves.
        return None
    # Weaver reads a local folder whole: it keeps only ``source`` and
    # ignores any ``@refspec`` or ``[sub_folder]`` that follows it.
    local = _local(source, root)
    if local is None or not local.is_dir():
        # A manifest file, maybe a published one.
        return None
    return local


def _definitions(root: Path, cache: Path) -> list[tuple[str, Path]]:
    """The YAML files weaver reads under ``root``, by their path within it.

    Like weaver with ``--follow-symlinks=false``, this doesn't go into a
    symlinked folder, and skips a link that leads to no file. A cache inside
    ``root`` is left out, since the runner generates files there.
    """
    found: list[tuple[str, Path]] = []
    for directory, folders, files in os.walk(root):
        if Path(directory) == cache:
            folders[:] = []
            continue
        folders[:] = [f for f in folders if not f.startswith(".")]
        relative = Path(directory).relative_to(root)
        for file in files:
            path = Path(directory, file)
            if (
                not file.startswith(".")
                and file.endswith(_DEFINITIONS)
                and path.is_file()
            ):
                found.append(((relative / file).as_posix(), path))
    return sorted(found)


def _dependencies(root: Path) -> list[dict[str, Any]] | None:
    """The dependencies ``root``'s manifest declares.

    ``None`` when the manifest is a published one: weaver reads the resolved
    registry it points at instead of anything here.
    """
    for name in _MANIFESTS:
        manifest = root / name
        if manifest.is_file():
            loaded = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                return []
            fields = cast("dict[str, object]", loaded)
            if fields.get("file_format") == _PUBLISHED or any(
                key in fields
                for key in ("resolved_registry_uri", "resolved_schema_uri")
            ):
                return None
            declared = fields.get("dependencies")
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
    """Run weaver over ``registry``; the model it wrote, while it exists.

    Weaver also reads the first ``.weaver.toml`` above the working directory,
    whose ``[registry]`` settings change what is resolved. Neither is part of
    a cached model's name, so both are passed here with weaver's defaults.
    Its schema URL overrides keep the model out of the cache instead.
    """
    check_weaver()

    with tempfile.TemporaryDirectory() as generated:
        completed = subprocess.run(  # noqa: S603
            [
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
