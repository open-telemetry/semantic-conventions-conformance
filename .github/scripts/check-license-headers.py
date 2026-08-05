#!/usr/bin/env python3
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Verify that every source file carries the Apache-2.0 license header.

The OpenTelemetry contribution guide asks for license information in all source
files where applicable, using the ``Copyright The OpenTelemetry Authors`` notice
form recommended by the CNCF. This repo uses the two-line short form that
``opentelemetry-python`` uses::

    # Copyright The OpenTelemetry Authors
    # SPDX-License-Identifier: Apache-2.0

Run from the repo root::

    python .github/scripts/check-license-headers.py

Formats without comment syntax (JSON) and generated lock files are excluded:
a file is checked only if its suffix appears in ``COMMENT_PREFIXES``.

This is a script rather than ruff's ``CPY001`` because that rule is preview-only
and Python-only, while scenario code here will span many languages.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

COPYRIGHT_LINE = "Copyright The OpenTelemetry Authors"
SPDX_LINE = "SPDX-License-Identifier: Apache-2.0"

# Suffix -> comment prefix. A file is checked if and only if its suffix appears
# here, so new file types are opted in explicitly rather than by accident.
# Deliberately kept broader than the languages present today: an entry costs
# nothing, whereas a missing one means a new language's files silently go
# unchecked until someone notices.
COMMENT_PREFIXES: dict[str, str] = {
    ".cs": "//",
    ".ex": "#",
    ".exs": "#",
    ".go": "//",
    ".java": "//",
    ".js": "//",
    ".kts": "//",
    ".mjs": "//",
    ".php": "//",
    ".py": "#",
    ".rb": "#",
    ".rs": "//",
    ".sh": "#",
    ".swift": "//",
    ".ts": "//",
}

# Lines allowed to appear before the header: a shebang, a PHP open tag, or
# blank lines. Anything else means the header is buried below real code.
PREAMBLE_PREFIXES = ("#!", "<?php")


def tracked_files() -> list[Path]:
    """All files git knows about, including new ones not yet committed."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def has_header(path: Path, prefix: str) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    lines = [line.strip() for line in text.splitlines()]
    start = 0
    while start < len(lines) and (not lines[start] or lines[start].startswith(PREAMBLE_PREFIXES)):
        start += 1

    return lines[start : start + 2] == [f"{prefix} {COPYRIGHT_LINE}", f"{prefix} {SPDX_LINE}"]


def main() -> int:
    missing: list[Path] = []
    for path in tracked_files():
        prefix = COMMENT_PREFIXES.get(path.suffix)
        if prefix is None or not path.is_file():
            continue
        if not has_header(path, prefix):
            missing.append(path)

    if not missing:
        return 0

    print("Missing Apache-2.0 license header:", file=sys.stderr)
    for path in sorted(missing):
        print(f"  {path.as_posix()}", file=sys.stderr)
    print(
        "\nAdd the following as the first lines (after any shebang):\n"
        f"  <comment> {COPYRIGHT_LINE}\n"
        f"  <comment> {SPDX_LINE}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
