# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance runs against the GenAI semantic conventions.

The whole domain: the ``semantic-conventions-genai`` registry at a pinned SHA,
the advice policies that check it, and how to recognise a GenAI span.
Everything a directory declaring ``runner: genai-conformance`` then gets is
the runner's :class:`~.Domain`.

The mock LLM server is not part of it: a directory declares the one it talks
to under ``server:``.
"""

import shutil
from pathlib import Path

from opentelemetry.conformance import Domain, cache_dir, require_pin

from ._coverage import classifier

_HERE = Path(__file__).parent

_UNFETCHABLE_REF = '"$ref": "http://json-schema.org/draft-07/schema#"'


def _advice_data(registry: Path) -> str:
    """A ``--advice-data`` glob of the GenAI content JSON schemas.

    The schemas are copied out of the registry before being handed to weaver,
    because gen-ai-tool-definitions.json references the external draft-07
    meta-schema, which weaver's rego engine refuses to fetch at eval time, and
    the $ref has to be rewritten to a local object. The registry may be
    somebody's working tree, which is not ours to edit — so the rewrite
    happens on the copy. Rebuilt each time, since the source moves whenever
    the registry does.
    """
    source = registry / "gen-ai"
    staged = cache_dir() / "advice-data" / "genai"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    for schema in sorted(source.glob("*.json")):
        text = schema.read_text(encoding="utf-8")
        (staged / schema.name).write_text(
            text.replace(_UNFETCHABLE_REF, '"type": "object"'),
            encoding="utf-8",
        )
    return str(staged / "*.json")


DOMAIN = Domain(
    name="genai-conformance",
    repo="open-telemetry/semantic-conventions-genai",
    ref=require_pin(_HERE / "versions.env", "SEMCONV_GENAI_REF"),
    classifier=classifier,
    policies=_HERE / "policies",
    advice_data=_advice_data,
)

# Named in pyproject.toml: the runner entry point and the console script.
genai_session = DOMAIN.session
cli = DOMAIN.cli

__all__ = ["DOMAIN", "cli", "genai_session"]
