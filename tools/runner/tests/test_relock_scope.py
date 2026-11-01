# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Which ecosystems a Renovate PR's lock files are regenerated for."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from opentelemetry.conformance import _relock_scope
from opentelemetry.conformance._relock_scope import (
    ECOSYSTEMS,
    ecosystems,
    matrix,
)


@pytest.mark.parametrize(
    ("paths", "expected"),
    [
        # The workflow that pins every toolchain: every lock may move.
        ([".github/workflows/runner.yml"], list(ECOSYSTEMS)),
        # Other workflows set up no toolchain.
        ([".github/workflows/codeql.yml"], []),
        # The #186 breakage started in a tools/ manifest.
        (["tools/js/scenario-sdk/package.json"], ["js"]),
        (["tools/go/go.mod", "tools/go/go.sum"], ["go"]),
        (
            ["scenarios/gen-ai/python/agno/openinference/pyproject.toml"],
            ["python"],
        ),
        (["scenarios/http/python/flask/x/server/uv.lock"], ["python"]),
        (["tools/ruby/scenario-sdk/Gemfile"], ["ruby"]),
        (["tools/ruby/scenario-sdk/x.gemspec"], ["ruby"]),
        (["tools/http/test-client/ruby/Gemfile.lock"], ["ruby"]),
        (["scenarios/http/php/slim/opentelemetry-slim/composer.json"], ["php"]),
        (["tools/php/scenario/composer.lock"], ["php"]),
        # Ecosystems without lock files, and pins no lock file embeds.
        (
            [
                "scenarios/http/java/gradle/libs.versions.toml",
                "tools/dotnet/Directory.Packages.props",
                "tools/runner/src/opentelemetry/conformance/versions.env",
            ],
            [],
        ),
        # A union comes back in the canonical order, not the input order.
        (
            ["tools/php/scenario/composer.json", "tools/go/go.mod"],
            ["go", "php"],
        ),
        ([], []),
    ],
)
def test_changed_files_map_to_ecosystems(
    paths: list[str], expected: list[str]
) -> None:
    assert ecosystems(paths) == expected


def test_nothing_to_do_is_an_empty_string() -> None:
    """The workflow skips `relock` on exactly this value."""
    assert matrix(["README.md"]) == ""


def test_the_matrix_is_compact_json() -> None:
    assert matrix(["tools/go/go.mod", "tools/js/scenario-sdk/package.json"]) == (
        '{"include":[{"ecosystem":"js"},{"ecosystem":"go"}]}'
    )


def test_it_runs_by_file_path_without_the_package() -> None:
    """CI runs it with the runner image's bare python3: importing the
    package would pull in the whole runner and its dependencies."""
    script = Path(_relock_scope.__file__)
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-I", str(script)],
        input="tools/go/go.mod\n\n",
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout == '{"include":[{"ecosystem":"go"}]}\n'
