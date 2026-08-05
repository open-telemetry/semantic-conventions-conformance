# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Mapping between scenario ids, data files, and result directories."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScenarioLocation:
    lang: str
    library: str
    ecosystem: str

    @property
    def scenario_id(self) -> str:
        """Dash-joined display form of the triple.

        Used for log lines, error messages, HTML anchors, and CI artifact
        names. The string form is deliberately one-way: all parsing goes
        through :meth:`from_results_dir` / :meth:`from_data_file`, which work
        off the filesystem layout and cannot be confused by slugs that
        contain hyphens. Pass ``ScenarioLocation`` (or ``lang`` / ``library``
        / ``ecosystem`` separately) through code paths; only use this
        property when a single string is required for display.
        """
        return f"{self.lang}-{self.library}-{self.ecosystem}"

    def data_file(self, domain_dir: Path) -> Path:
        return domain_dir / self.lang / self.library / f"data-{self.ecosystem}.json"

    def results_dir(self, domain_dir: Path) -> Path:
        return domain_dir / self.lang / self.library / "results" / self.ecosystem

    @classmethod
    def from_results_dir(cls, result_dir: Path, domain_dir: Path) -> ScenarioLocation:
        relative = result_dir.relative_to(domain_dir)
        lang, library, _, ecosystem = relative.parts
        return cls(lang=lang, library=library, ecosystem=ecosystem)

    @classmethod
    def from_data_file(cls, data_file: Path, domain_dir: Path) -> ScenarioLocation:
        relative = data_file.relative_to(domain_dir)
        if len(relative.parts) != 3:
            raise ValueError(
                f"Expected data file under <domain>/<lang>/<library>/data-<ecosystem>.json, got {relative}"
            )
        lang, library, data_name = relative.parts
        if not data_name.startswith("data-"):
            raise ValueError(f"Expected data file name starting with 'data-': {relative}")
        return cls(
            lang=lang,
            library=library,
            ecosystem=Path(data_name).stem.removeprefix("data-"),
        )


def iter_scenario_locations(
    domain_dir: Path,
    *,
    language: str | None = None,
    library: str | None = None,
) -> Iterator[ScenarioLocation]:
    """Yield `ScenarioLocation`s discovered via `data-*.json` under `domain_dir`.

    Single source of truth for the "glob `<lang>/<lib>/data-*.json`, parse
    library from parent dir, parse ecosystem from stem" pattern. Pass
    `language` to restrict to one language, and additionally `library` to
    restrict to a single library dir. Results are deterministic (sorted).
    """
    if library is not None and language is None:
        raise ValueError("library filter requires a language filter")

    if language is None:
        pattern = "*/*/data-*.json"
    elif library is None:
        pattern = f"{language}/*/data-*.json"
    else:
        pattern = f"{language}/{library}/data-*.json"

    for data_file in sorted(domain_dir.glob(pattern)):
        yield ScenarioLocation.from_data_file(data_file, domain_dir)
