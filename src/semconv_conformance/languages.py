# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Language registry: canonical language order, display names, and CI runners.

Single source of truth is `<repo_root>/languages.json`. A language is
"supported" by a domain when `<domain_dir>/<language>/` exists on disk —
there's no separate per-domain list to keep in sync.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

DEFAULT_RUNNER = "ubuntu-latest"

_REGISTRY_PATH = Path(__file__).resolve().parent / "languages.json"


@cache
def _registry() -> dict[str, dict[str, str]]:
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


def supported_languages(domain_dir: Path) -> tuple[str, ...]:
    """Languages with a subdirectory under `domain_dir`, in registry order."""
    return tuple(lang for lang in _registry() if (domain_dir / lang).is_dir())


def language_display_names(domain_dir: Path) -> dict[str, str]:
    registry = _registry()
    return {lang: registry[lang]["display_name"] for lang in registry if (domain_dir / lang).is_dir()}


def default_runner(language: str) -> str:
    return _registry().get(language, {}).get("runner", DEFAULT_RUNNER)
