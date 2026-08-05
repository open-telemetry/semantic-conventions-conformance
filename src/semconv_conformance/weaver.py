# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Weaver binary management: version pinning, download, and caching."""

from __future__ import annotations

import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VERSIONS_FILE = REPO_ROOT / "versions.env"

logger = logging.getLogger(__name__)


def _load_version_pins() -> dict[str, str]:
    """Load shared external version pins from the repository root."""
    try:
        content = VERSIONS_FILE.read_text(encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Could not read version pins file: {VERSIONS_FILE}") from e

    pins: dict[str, str] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            raise RuntimeError(f"Invalid version pin line in {VERSIONS_FILE}: {raw_line!r}")
        pins[key.strip()] = value.strip().strip('"').strip("'")

    return pins


VERSION_PINS = _load_version_pins()
WEAVER_VERSION = VERSION_PINS["WEAVER_VERSION"]
SEMCONV_VERSION = VERSION_PINS["SEMCONV_VERSION"]
#: Per-read socket timeout for the Weaver release download, so a stalled
#: network fails the run instead of hanging CI until the job times out.
DOWNLOAD_TIMEOUT_SECONDS = 60


def _normalize_version(version: str) -> str:
    """Normalize optional leading-v version strings for comparisons."""
    return version[1:] if version.startswith("v") else version


def path_from_env(var_name: str, default_path: Path) -> Path:
    value = os.environ.get(var_name)
    if value:
        return Path(value)
    return default_path


def _weaver_binary_name() -> str:
    """Return the platform-specific Weaver binary name."""
    return "weaver.exe" if sys.platform == "win32" else "weaver"


def _weaver_asset_name() -> str:
    """Return the pinned Weaver release asset name for the current platform."""
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in {"amd64", "x86_64"}:
        return "weaver-x86_64-pc-windows-msvc.zip"
    if sys.platform == "linux" and machine in {"amd64", "x86_64"}:
        return "weaver-x86_64-unknown-linux-gnu.tar.xz"
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        return "weaver-aarch64-apple-darwin.tar.xz"
    if sys.platform == "darwin" and machine in {"amd64", "x86_64"}:
        return "weaver-x86_64-apple-darwin.tar.xz"
    raise RuntimeError(f"Unsupported platform for managed Weaver install: {sys.platform} / {platform.machine()}")


def _find_weaver_binary(search_root: Path) -> Path | None:
    """Return the first Weaver binary found under the given directory."""
    for path in search_root.rglob(_weaver_binary_name()):
        if path.is_file():
            return path
    return None


def _weaver_version(binary: str | Path) -> str:
    """Return the normalized version reported by a Weaver binary, or an empty string."""
    try:
        proc = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""

    output = f"{proc.stdout}\n{proc.stderr}"
    match = re.search(r"\bv?(\d+\.\d+\.\d+)\b", output)
    return match.group(1) if match else ""


def _download_file(url: str, destination: Path) -> None:
    """Download a file over HTTPS from github.com to disk."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise RuntimeError(f"Refusing to download non-github.com URL: {url}")
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
        # Release assets redirect to GitHub's CDN, so the final host is not
        # github.com. Only the scheme is re-checked, to catch a redirect that
        # would otherwise downgrade the transfer to plaintext HTTP.
        final_url = response.geturl()
        if urllib.parse.urlparse(final_url).scheme != "https":
            raise RuntimeError(f"Refusing to follow non-HTTPS redirect to: {final_url}")
        with destination.open("wb") as out:
            shutil.copyfileobj(response, out)


def _extract_archive(archive_path: Path, extract_dir: Path) -> None:
    """Extract `archive_path` into `extract_dir`, rejecting members that escape it."""
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as zip_archive:
            for name in zip_archive.namelist():
                resolved = (extract_dir / name).resolve()
                if not resolved.is_relative_to(extract_dir.resolve()):
                    raise RuntimeError(f"Refusing to extract archive member outside target dir: {name}")
            zip_archive.extractall(extract_dir)
    else:
        with tarfile.open(archive_path, "r:*") as tar_archive:
            # `data` rejects absolute paths, `..` traversal, links pointing
            # outside the destination, and special file types.
            tar_archive.extractall(extract_dir, filter="data")


def ensure_weaver() -> Path:
    """Ensure the pinned Weaver version is available and return its binary path."""
    expected_version = _normalize_version(WEAVER_VERSION)

    system_weaver = shutil.which(_weaver_binary_name())
    if system_weaver and _weaver_version(system_weaver) == expected_version:
        return Path(system_weaver)

    cache_root = path_from_env(
        "WEAVER_CACHE",
        Path.home() / ".cache" / "otel-conformance" / "weaver",
    )
    install_dir = cache_root / WEAVER_VERSION.replace("/", "_")
    cached_binary = _find_weaver_binary(install_dir) if install_dir.exists() else None
    if cached_binary and _weaver_version(cached_binary) == expected_version:
        return cached_binary

    asset_name = _weaver_asset_name()
    download_url = f"https://github.com/open-telemetry/weaver/releases/download/{WEAVER_VERSION}/{asset_name}"
    install_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        dir=str(install_dir.parent),
        prefix=f"weaver-{expected_version}-",
    ) as tmp:
        tmp_path = Path(tmp)
        archive_path = tmp_path / asset_name
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        logger.info("Downloading Weaver %s", WEAVER_VERSION)
        _download_file(download_url, archive_path)

        _extract_archive(archive_path, extract_dir)

        extracted_binary = _find_weaver_binary(extract_dir)
        if extracted_binary is None:
            raise RuntimeError(f"Downloaded Weaver archive did not contain {_weaver_binary_name()}")

        if install_dir.exists():
            shutil.rmtree(install_dir)
        shutil.copytree(extract_dir, install_dir)

    cached_binary = _find_weaver_binary(install_dir)
    if cached_binary is None:
        raise RuntimeError(f"Installed Weaver binary not found under {install_dir}")
    if sys.platform != "win32":
        cached_binary.chmod(cached_binary.stat().st_mode | 0o111)
    installed_version = _weaver_version(cached_binary)
    if installed_version != expected_version:
        raise RuntimeError(
            f"Installed Weaver version mismatch: expected {WEAVER_VERSION}, found {installed_version or 'unknown'}"
        )
    return cached_binary


def ensure_semconv_registry() -> str:
    """Ensure the pinned semconv registry is cached locally and return its model dir path."""
    registry = os.environ.get("REGISTRY")
    if registry:
        return registry

    semconv_cache_root = path_from_env(
        "SEMCONV_CACHE",
        Path.home() / ".cache" / "otel-conformance" / "semconv",
    )
    semconv_cache = semconv_cache_root / SEMCONV_VERSION.replace("/", "_")
    model_dir = semconv_cache / "model"

    if not model_dir.is_dir():
        logger.info("Caching semantic conventions registry (%s)", SEMCONV_VERSION)
        # An interrupted clone leaves `semconv_cache` present but without
        # `model/`. `git clone` refuses to write into a non-empty directory,
        # so the cache would stay wedged until deleted by hand.
        if semconv_cache.exists():
            shutil.rmtree(semconv_cache)
        semconv_cache.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "git",
                "clone",
                "--branch",
                SEMCONV_VERSION,
                "--depth",
                "1",
                "-q",
                "https://github.com/open-telemetry/semantic-conventions.git",
                str(semconv_cache),
            ],
            check=True,
        )

    return str(model_dir)
