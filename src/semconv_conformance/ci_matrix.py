# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Generate the GitHub Actions scenario matrix for one or both conformance domains.

Exposed as the `semconv-ci-matrix` console script and consumed by
`.github/workflows/conformance-ci.yml` via `fromJson(...)`.

Discovery globs `<domain>/<language>/<library>/data-*.json` via
:func:`semconv_conformance.locations.iter_scenario_locations`, so the
matrix stays in sync with committed scenarios with no hand-maintained list.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from semconv_conformance.languages import default_runner, supported_languages
from semconv_conformance.locations import iter_scenario_locations

REPO_ROOT = Path(__file__).resolve().parents[2]
#: Domains with scenarios in the repo. Extend as each domain lands.
DOMAINS = ("http",)
#: `ci_runs_on` values a scenario may request. Restricted to GitHub-hosted
#: labels so a scenario's metadata.json can't route its job onto an
#: unexpected runner.
ALLOWED_RUNNERS = frozenset(
    {
        "ubuntu-latest",
        "ubuntu-24.04",
        "ubuntu-24.04-arm",
        "ubuntu-22.04",
        "ubuntu-22.04-arm",
        "windows-latest",
        "windows-2025",
        "windows-2022",
        "macos-latest",
        "macos-15",
        "macos-14",
        "macos-13",
    }
)


def _load_json(path: Path) -> object:
    """Read JSON from `path` and raise a filename-annotated error on parse failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"error: invalid JSON in {path}: {e}") from e


def _require_metadata(scenario_dir: Path, domain: str, language: str, library: str) -> dict[str, object]:
    metadata_file = scenario_dir / "metadata.json"
    if not metadata_file.is_file():
        raise SystemExit(
            f"error: missing metadata.json for {domain}/{language}/{library} "
            f"(every scenario directory must declare metadata.json with a display_name)"
        )
    metadata = _load_json(metadata_file)
    if not isinstance(metadata, dict):
        raise SystemExit(f"error: {metadata_file} must contain a JSON object")
    display_name = metadata.get("display_name")
    if not isinstance(display_name, str) or not display_name.strip():
        raise SystemExit(f"error: {metadata_file} is missing a non-empty string display_name")
    return metadata


def _runner_for_scenario(metadata: dict[str, object], language: str, metadata_file: Path) -> str:
    runner = metadata.get("ci_runs_on")
    if runner is None:
        return default_runner(language)
    if not isinstance(runner, str) or runner not in ALLOWED_RUNNERS:
        raise SystemExit(
            f"error: {metadata_file} requests ci_runs_on={runner!r}, which is not one of "
            f"{', '.join(sorted(ALLOWED_RUNNERS))}"
        )
    return runner


def _discover_scenarios(domain: str, repo_root: Path) -> list[dict[str, str]]:
    domain_dir = repo_root / domain
    entries: list[dict[str, str]] = []
    for language in supported_languages(domain_dir):
        for loc in iter_scenario_locations(domain_dir, language=language):
            scenario_dir = domain_dir / loc.lang / loc.library
            metadata = _require_metadata(scenario_dir, domain, language, loc.library)
            entries.append(
                {
                    "domain": domain,
                    "language": language,
                    "lib": loc.library,
                    "eco": loc.ecosystem,
                    "runner": _runner_for_scenario(metadata, language, scenario_dir / "metadata.json"),
                }
            )
    return entries


def build_matrix(domain: str, repo_root: Path = REPO_ROOT) -> dict[str, list[dict[str, str]]]:
    """Return the `{"include": [...]}` matrix for `domain` or `"all"`."""
    domains = DOMAINS if domain == "all" else (domain,)
    entries: list[dict[str, str]] = []
    for d in domains:
        entries.extend(_discover_scenarios(d, repo_root))
    return {"include": entries}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", choices=(*DOMAINS, "all"))
    args = parser.parse_args(argv)

    matrix = build_matrix(args.domain)
    if not matrix["include"]:
        print(f"error: generated an empty matrix for domain {args.domain!r}", file=sys.stderr)
        return 1
    print(f"matrix={json.dumps(matrix, separators=(',', ':'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
