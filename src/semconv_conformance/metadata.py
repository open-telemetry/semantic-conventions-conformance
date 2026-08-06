# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Shared ecosystem, library, and dependency metadata loaders."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

DependencyVersionReader = Callable[[Path, str], dict[str, str]]


class MetadataError(Exception):
    """Raised when a committed metadata file is unreadable, malformed, or the wrong shape."""


def load_json_object(path: Path) -> dict[str, object]:
    """Parse `path` as a JSON object, annotating every failure with the file name.

    These files are hand-authored by contributors adding a scenario, so a bare
    `JSONDecodeError` with no path is a poor first-run experience.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        raise MetadataError(f"could not read {path}: {e}") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise MetadataError(f"invalid JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise MetadataError(f"{path} must contain a JSON object, got {type(data).__name__}")
    return data


def _require_str(value: object, path: Path, what: str) -> str:
    if not isinstance(value, str):
        raise MetadataError(f"{path}: {what} must be a string, got {type(value).__name__}")
    return value


def _read_python_dependency_versions(scenario_dir: Path, ecosystem: str) -> dict[str, str]:
    versions: dict[str, str] = {}
    req_file = scenario_dir / f"requirements-{ecosystem}.txt"
    if not req_file.exists():
        return versions
    for line in req_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "==" not in line:
            continue
        pkg, ver = line.split("==", 1)
        versions[pkg.strip()] = ver.strip()
    return versions


# One reader per language. Each language's PR adds its reader alongside its
# adapter and scenarios.
ALL_DEPENDENCY_VERSION_READERS: dict[str, DependencyVersionReader] = {
    "python": _read_python_dependency_versions,
}


class DomainMetadata:
    """Load and expose metadata for one conformance domain."""

    def __init__(
        self,
        *,
        domain_dir: Path,
        language_display_names: dict[str, str],
        dependency_version_readers: dict[str, DependencyVersionReader],
    ) -> None:
        self.domain_dir = domain_dir
        self.language_display_names = dict(language_display_names)
        self.language_slugs = {display: slug for slug, display in self.language_display_names.items()}
        self.dependency_version_readers = dict(dependency_version_readers)
        self.ecosystem_display, self.ecosystem_repos = self._load_ecosystems()
        self.library_display_names, self.library_repos = self._discover_library_metadata()
        self._scenario_metadata_cache: dict[tuple[str, str], dict[str, object]] = {}

    def _load_ecosystems(self) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
        eco_file = self.domain_dir / "ecosystems.json"
        if not eco_file.is_file():
            return {}, {}

        data = load_json_object(eco_file)
        display: dict[str, str] = {}
        repos: dict[tuple[str, str], str] = {}
        for eco, info in data.items():
            if not isinstance(info, dict):
                raise MetadataError(f"{eco_file}: ecosystem {eco!r} must map to a JSON object")
            display[eco] = _require_str(info.get("display_name", eco), eco_file, f"ecosystem {eco!r} 'display_name'")
            eco_repos = info.get("repos", {})
            if not isinstance(eco_repos, dict):
                raise MetadataError(f"{eco_file}: 'repos' for ecosystem {eco!r} must be a JSON object")
            for lang_slug, repo in eco_repos.items():
                slug = _require_str(lang_slug, eco_file, f"'repos' key for ecosystem {eco!r}")
                lang_display = self.language_display_names.get(slug, slug)
                repos[(eco, lang_display)] = _require_str(repo, eco_file, f"'repos.{slug}' for ecosystem {eco!r}")
        return display, repos

    def _discover_library_metadata(self) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
        names: dict[str, str] = {}
        repos: dict[tuple[str, str], str] = {}
        if not self.domain_dir.is_dir():
            return names, repos

        for lang_dir in sorted(self.domain_dir.iterdir()):
            if not lang_dir.is_dir() or lang_dir.name not in self.language_display_names:
                continue
            for lib_dir in sorted(lang_dir.iterdir()):
                if not lib_dir.is_dir():
                    continue
                meta = lib_dir / "metadata.json"
                if not meta.is_file():
                    continue
                data = load_json_object(meta)
                slug = lib_dir.name
                if "display_name" in data and slug not in names:
                    names[slug] = _require_str(data["display_name"], meta, "'display_name'")
                if "repo" in data:
                    repos[(lang_dir.name, slug)] = _require_str(data["repo"], meta, "'repo'")
        return names, repos

    def library_display_name(self, slug: str) -> str:
        return self.library_display_names.get(slug, slug)

    def _load_scenario_metadata(self, lang: str, library: str) -> dict[str, object]:
        key = (lang, library)
        if key not in self._scenario_metadata_cache:
            meta_file = self.domain_dir / lang / library / "metadata.json"
            if not meta_file.is_file():
                self._scenario_metadata_cache[key] = {}
            else:
                self._scenario_metadata_cache[key] = load_json_object(meta_file)
        return self._scenario_metadata_cache[key]

    def required_opt_in_env_var(self, lang: str, library: str, ecosystem: str) -> str:
        metadata = self._load_scenario_metadata(lang, library)
        opt_in_env_vars = metadata.get("opt_in_env_vars", {})
        if not isinstance(opt_in_env_vars, dict):
            return ""
        env_var = opt_in_env_vars.get(ecosystem, "")
        return env_var if isinstance(env_var, str) else ""

    def _version_package_from_metadata(self, lang: str, library: str, ecosystem: str) -> str:
        metadata = self._load_scenario_metadata(lang, library)
        version_packages = metadata.get("version_packages", {})
        if not isinstance(version_packages, dict):
            return ""
        package_name = version_packages.get(ecosystem, "")
        return package_name if isinstance(package_name, str) else ""

    def _read_deps_from_scenario_dir(self, lang: str, library: str, ecosystem: str) -> dict[str, str]:
        reader = self.dependency_version_readers.get(lang)
        if reader is None:
            return {}
        return reader(self.domain_dir / lang / library, ecosystem)

    def extract_version_from_deps(self, lang: str, library: str, ecosystem: str) -> str:
        versions = self._read_deps_from_scenario_dir(lang, library, ecosystem)
        package_name = self._version_package_from_metadata(lang, library, ecosystem)
        if not package_name:
            return ""
        return versions.get(package_name, "")
