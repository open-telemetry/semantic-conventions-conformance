# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Fetching a pinned semantic-convention registry.

A registry is a GitHub checkout at a pinned ref, not something a package can
commit, so it is fetched into a cache and reused. Which repo and which ref are
the caller's — this module only knows how to put one on disk.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Bounds the fetch so a slow or unreachable GitHub doesn't hang a run until
# the OS-level socket timeout.
_FETCH_TIMEOUT_SECONDS = 60
_VERSION_TIMEOUT_SECONDS = 10

_GITHUB = "https://github.com/"

# Weaver's registry-as-git-URL syntax: <url>.git, optionally @<ref>, optionally
# [<sub folder>]. See the --registry argument of any weaver command. The scheme
# is what tells it apart from a local checkout named `<something>.git`.
_GIT_REGISTRY = re.compile(
    r"^(?P<url>[a-zA-Z][a-zA-Z0-9+.-]*://[^\s\[\]]+\.git)"
    r"(?:@(?P<ref>[^\s\[\]]+))?"
    r"(?:\[(?P<sub_folder>[^\]]+)\])?$"
)


def load_version_pins(path: Path) -> dict[str, str]:
    """Read a ``versions.env`` file into a mapping."""
    pins: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise RuntimeError(f"Invalid version pin in {path}: {raw_line!r}")
        pins[key.strip()] = value.strip().strip('"').strip("'")
    return pins


def require_pin(path: Path, name: str) -> str:
    """Read one pin, saying where to fix it when it isn't there."""
    pins = load_version_pins(path)
    try:
        return pins[name]
    except KeyError:
        raise RuntimeError(f"{path} is missing the pin {name}") from None


@dataclass(frozen=True)
class GitRegistry:
    """A registry declared as a git URL rather than as a path on disk."""

    url: str
    ref: str | None = None
    sub_folder: str | None = None

    @property
    def repo(self) -> str:
        """The ``org/name`` to fetch an archive of."""
        if not self.url.startswith(_GITHUB):
            raise RuntimeError(
                f"{self.url}: a registry URL is fetched as a GitHub archive, "
                "so only github.com URLs work here"
            )
        return self.url[len(_GITHUB) :].removesuffix(".git")


def parse_git_registry(value: str) -> GitRegistry | None:
    """Read ``<url>.git@<ref>[<sub folder>]``; None if it isn't one."""
    match = _GIT_REGISTRY.match(value.strip())
    if match is None:
        return None
    return GitRegistry(**match.groupdict())


def local_registry(value: str) -> Path:
    """A declared registry as a directory, fetching it when it is a git URL.

    Weaver takes a URL itself, but a domain's advice data is built by reading
    files out of the registry, which no weaver command hands back. So a URL is
    fetched once here and everything downstream sees an ordinary checkout.
    """
    declared = parse_git_registry(value)
    if declared is None:
        return Path(value)
    repo = declared.repo
    # No ref is the default branch, which is what GitHub serves for HEAD.
    checkout = provision(
        repo, declared.ref or "HEAD", label=repo.rpartition("/")[2]
    )
    return checkout / declared.sub_folder if declared.sub_folder else checkout


def cache_dir() -> Path:
    """Where fetched registries live. ``SEMCONV_CACHE`` overrides it."""
    override = os.environ.get("SEMCONV_CACHE")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "otel-conformance" / "semconv"


def provision(repo: str, ref: str, *, label: str) -> Path:
    """Fetch ``github.com/<repo>`` at ``ref`` into the cache; return its root.

    ``label`` names the checkout in the cache and in log messages, so two
    registries at the same ref don't collide. A completed fetch leaves a stamp
    file, which is what makes this a no-op on every later run.
    """
    target = cache_dir() / _safe_name(f"{label}-{ref}")
    stamp = target / ".provisioned"
    if stamp.is_file():
        return target

    url = f"https://github.com/{repo}/archive/{ref}.tar.gz"
    _download_and_extract(url, target, label=label)
    stamp.touch()
    return target


def _safe_name(value: str) -> str:
    """``value`` as one path component: a ref can hold slashes and worse."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", value)


def _download_and_extract(url: str, target: Path, *, label: str) -> None:
    """Download a ``.tar.gz`` and move its single top-level directory to ``target``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=str(target.parent), prefix=f"{label}-"
    ) as tmp:
        archive = Path(tmp) / "src.tar.gz"
        extracted = Path(tmp) / "extract"
        extracted.mkdir()

        logger.info("Fetching %s from %s", label, url)
        try:
            with (
                urllib.request.urlopen(  # noqa: S310
                    url, timeout=_FETCH_TIMEOUT_SECONDS
                ) as response,
                archive.open("wb") as out,
            ):
                shutil.copyfileobj(response, out)
        except (TimeoutError, urllib.error.URLError) as error:
            raise RuntimeError(
                f"Failed to fetch {label} from {url}: {error}"
            ) from error
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(extracted, filter="data")

        roots = [entry for entry in extracted.iterdir() if entry.is_dir()]
        if len(roots) != 1:
            raise RuntimeError(
                f"Unexpected layout in the {label} archive: "
                f"{[entry.name for entry in roots]}"
            )
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(roots[0]), str(target))


_PINS = Path(__file__).parent / "versions.env"


def weaver_version() -> str:
    """The weaver release this repo pins."""
    return require_pin(_PINS, "WEAVER_VERSION")


class WeaverNotInstalledError(RuntimeError):
    """No ``weaver`` on PATH, so nothing can be checked."""


@cache
def check_weaver(*, required: bool = True) -> None:
    """Refuse a run with no weaver; warn when it isn't the pinned version.

    A different version still works and is often what a maintainer wants, so
    that only warns — but the advice weaver gives is part of what a run
    records, and a mismatch explains a data file that moved for no other
    visible reason. Cached, so the warning is said once however many sessions
    a process opens.
    """
    installed = _installed_weaver_version()
    if installed is None:
        if not required:
            return
        raise WeaverNotInstalledError(
            "weaver is not on PATH — install the version pinned in "
            f"{_PINS.name} ({weaver_version()}) from "
            "https://github.com/open-telemetry/weaver/releases"
        )
    pinned = weaver_version()
    if installed != pinned.lstrip("v"):
        logger.warning(
            "weaver %s is on PATH, but the pin is %s — findings and coverage "
            "may differ from what CI records",
            installed,
            pinned,
        )


def _installed_weaver_version() -> str | None:
    """``weaver --version`` as a bare version, or None if it can't be read."""
    weaver = shutil.which("weaver")
    if weaver is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603
            [weaver, "--version"],
            capture_output=True,
            text=True,
            timeout=_VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    # "weaver 0.25.1"; a pin is written as a release tag, "v0.25.1".
    words = completed.stdout.split()
    return words[-1].lstrip("v") if words else None
