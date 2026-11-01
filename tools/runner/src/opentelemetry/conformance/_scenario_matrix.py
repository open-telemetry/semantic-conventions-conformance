# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Build the Runner matrix from tracked conformance.yaml paths on stdin.

Standard library only: discovery runs this file with the runner image's Python,
before installing the runner package.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from typing import Iterable, Mapping

# Change only these counts to resize the library-level CI shards.
SHARD_COUNTS = {"gen-ai-python": 4, "http-java": 4}


def matrix(
    paths: Iterable[str],
    shard_counts: Mapping[str, int] = SHARD_COUNTS,
) -> dict[str, list[dict[str, str]]]:
    for group, count in shard_counts.items():
        if type(count) is not int or count < 1:
            raise ValueError(f"invalid shard count for {group}: {count!r}")

    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in paths:
        parts = path.split("/")
        if (
            len(parts) < 4
            or parts[0] != "scenarios"
            or parts[-1] != "conformance.yaml"
            or any(part in ("", ".", "..") for part in parts)
        ):
            raise ValueError(f"unexpected conformance scenario path: {path}")
        domain, language = parts[1:3]
        group = f"{domain}-{language}"
        if language == "ruby":
            root = "/".join(parts[:-1])
        elif group in shard_counts:
            if len(parts) < 5:
                raise ValueError(f"missing library in scenario path: {path}")
            root = "/".join(parts[:4])
        else:
            root = "/".join(parts[:3])
        groups[domain, language].add(root)

    include: list[dict[str, str]] = []
    for (domain, language), roots in sorted(groups.items()):
        group = f"{domain}-{language}"
        ordered = sorted(roots)
        if language == "ruby":
            shards = [[root] for root in ordered]
        else:
            count = min(shard_counts.get(group, 1), len(ordered))
            shards = [ordered[index::count] for index in range(count)]
        for index, shard in enumerate(shards, 1):
            matrix_id = group
            if language == "ruby":
                matrix_id = shard[0].removeprefix("scenarios/").replace("/", "-")
            elif group in shard_counts:
                matrix_id += f"-shard-{index}"
            include.append(
                {
                    "domain": domain,
                    "language": language,
                    "matrix_id": matrix_id,
                    "scenario_roots": "\n".join(shard),
                    "cache_dependency_glob": "\n".join(
                        f"{root}/**/uv.lock" for root in shard
                    ),
                    "report_paths": "\n".join(
                        f"{root}/**/output/reports/**/*.json"
                        for root in shard
                    ),
                }
            )
    return {"include": include}


def main() -> int:
    try:
        result = matrix(line.rstrip("\n") for line in sys.stdin if line.strip())
        if not result["include"]:
            raise ValueError("no conformance scenarios found")
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
