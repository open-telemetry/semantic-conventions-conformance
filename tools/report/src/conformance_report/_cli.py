# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-report`` — build, check, or summarise the report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from ._aggregate import build, render
from ._markdown import render as render_summary
from ._markdown import render_diff

# Where the committed report lives, and where the site fetches it from.
DEFAULT_REPORT = Path("docs/data/conformance.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-report",
        description=(
            "Aggregate the committed conformance coverage into one report."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="the checkout to read scenarios from (default: cwd)",
    )
    verbs = parser.add_subparsers(dest="verb", required=True)

    writer = verbs.add_parser("build", help="write the report")
    writer.add_argument("--out", type=Path, default=DEFAULT_REPORT)

    verbs.add_parser(
        "check",
        help="fail if the committed report is not what a rebuild produces",
    )

    markdown = verbs.add_parser(
        "markdown", help="summarise the report for a job summary"
    )
    markdown.add_argument(
        "--against",
        type=Path,
        help=(
            "a report to diff against, so the summary says what moved rather "
            "than only where things stand"
        ),
    )
    return parser


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def cli(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root: Path = arguments.root.resolve()

    if arguments.verb == "build":
        content = render(build(root))
        out: Path = arguments.out
        _write(out if out.is_absolute() else root / out, content)
        return 0

    if arguments.verb == "check":
        expected = render(build(root))
        committed = root / DEFAULT_REPORT
        if not committed.is_file():
            print(
                f"{DEFAULT_REPORT} is missing — run "
                "`otel-conformance-report build`",
                file=sys.stderr,
            )
            return 1
        if committed.read_text(encoding="utf-8") != expected:
            print(
                f"{DEFAULT_REPORT} is out of date — run "
                "`otel-conformance-report build` and commit the result",
                file=sys.stderr,
            )
            return 1
        return 0

    document = build(root)
    summary = render_summary(document)
    if arguments.against is not None:
        before = json.loads(arguments.against.read_text(encoding="utf-8"))
        changes = render_diff(before, document)
        if changes:
            summary = f"{summary}\n{changes}"
    print(summary, end="")
    return 0
