# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The coverage model: what a registry declares, per signal and entity.

Weaver resolves a registry into one JSON file. Provider refinements
(``openai.inference.client`` refines ``gen_ai.inference.client``) are left out:
a provider's attributes are not coverage of the general span type::

    {"spans":    {"http.server": {"kind": "server", "attributes": {name: level}}},
     "events":   {name: {"attributes": {name: level}}},
     "metrics":  {name: {"attributes": {name: level}}},
     "entities": {name: {"identity": {name: level}, "description": {name: level}}}}

That is what a reduction reads to say which of a signal's declared attributes
a run actually carried.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
from functools import cache
from pathlib import Path
from typing import Any

from ._registry import check_weaver, weaver_version

logger = logging.getLogger(__name__)

_TEMPLATES = Path(__file__).parent / "weaver-templates"


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


def resolve(registry: Path, output: Path) -> Path:
    """Resolve ``registry`` into a coverage model at ``output``, once.

    ``output`` is expected to name the pin it belongs to, so moving a pin asks
    for a fresh model rather than silently reusing the old registry's.
    """
    if output.is_file():
        return output

    check_weaver()

    logger.info("Resolving the coverage model into %s", output)
    output.parent.mkdir(parents=True, exist_ok=True)
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
        # Moved rather than renamed: the temp directory is often another
        # filesystem from the cache.
        shutil.move(str(produced), output)
    return output


def load(path: Path) -> dict[str, dict[str, Any]]:
    """Read a resolved coverage model."""
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found — resolve the registry into a coverage model "
            "before reducing a run."
        )
    return json.loads(path.read_text(encoding="utf-8"))
