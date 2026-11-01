# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Tests for report generation, freshness checks and Markdown summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conformance_report import _aggregate, _cli, _markdown
from conftest import write_target

TARGET = "demo/python/demo/opentelemetry-demo"

# Every verb here builds, and building resolves a `runner:`.
pytestmark = pytest.mark.usefixtures("one_domain")


def build_into(root: Path) -> Path:
    assert _cli.cli(["--root", str(root), "build"]) == 0
    return root / _cli.DEFAULT_REPORT


def test_build_writes_the_report_where_the_site_reads_it(
    tmp_path: Path,
) -> None:
    write_target(tmp_path, TARGET)
    report = build_into(tmp_path)
    assert report.exists()
    document: dict[str, Any] = json.loads(report.read_text())
    assert document["schema_version"] == _aggregate.SCHEMA_VERSION
    assert [t["id"] for t in document["targets"]] == [TARGET]


def test_build_is_byte_identical_twice_over(tmp_path: Path) -> None:
    """`check` is a byte comparison, so this is what makes it usable."""
    write_target(tmp_path, TARGET)
    first = build_into(tmp_path).read_bytes()
    second = build_into(tmp_path).read_bytes()
    assert first == second


def test_check_passes_on_a_report_that_is_current(tmp_path: Path) -> None:
    write_target(tmp_path, TARGET)
    build_into(tmp_path)
    assert _cli.cli(["--root", str(tmp_path), "check"]) == 0


def test_check_fails_when_a_reduction_moved(tmp_path: Path) -> None:
    """The same shape as the repo's existing data.json freshness gate."""
    write_target(tmp_path, TARGET)
    build_into(tmp_path)
    write_target(
        tmp_path,
        TARGET,
        data={
            "spans": {"demo.client": ["demo.required"]},
            "events": {},
            "metrics": {},
            "entities": {},
            "findings": [],
        },
    )
    assert _cli.cli(["--root", str(tmp_path), "check"]) == 1


def test_check_fails_when_the_report_was_never_built(tmp_path: Path) -> None:
    write_target(tmp_path, TARGET)
    assert _cli.cli(["--root", str(tmp_path), "check"]) == 1


def test_check_fails_when_a_target_is_added(tmp_path: Path) -> None:
    """A new scenario has to be published, not silently left off the site."""
    write_target(tmp_path, TARGET)
    build_into(tmp_path)
    write_target(tmp_path, "demo/python/other/opentelemetry-other")
    assert _cli.cli(["--root", str(tmp_path), "check"]) == 1


def test_markdown_says_what_the_run_covered(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_target(tmp_path, TARGET)
    assert _cli.cli(["--root", str(tmp_path), "markdown"]) == 0
    printed = capsys.readouterr().out
    assert "Semantic-convention conformance" in printed
    assert "1 target, 0 findings." in printed
    assert "gzipped" in printed
    assert "open-telemetry/demo @ `v1.0.0` (`demo-conformance`)" in printed
    assert "Conformance changes" not in printed


def test_markdown_against_a_previous_report_says_what_moved(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_target(tmp_path, TARGET)
    report = build_into(tmp_path)
    against = ["markdown", "--against", str(report)]
    assert _cli.cli(["--root", str(tmp_path), *against]) == 0
    printed = capsys.readouterr().out
    assert "1 target, 0 findings (+0)." in printed
    assert "gzipped (+0 B)" in printed
    assert printed.endswith("No conformance changes.\n")


@pytest.mark.parametrize(
    "field, value",
    [
        (
            "signals",
            [{"type": "span", "name": "demo.client", "emitted": ["a"]}],
        ),
        ("findings", [{"id": "unit_mismatch"}]),
    ],
)
def test_target_changes_are_summarised_without_details(
    field: str, value: list[dict[str, Any]]
) -> None:
    target = {"id": TARGET, "signals": [], "findings": []}
    changes = _markdown.render_diff(
        {"targets": [target]},
        {"targets": [{**target, field: value}]},
    )
    assert changes == "### Conformance changes\n\n- 1 target changed\n"


def test_target_additions_and_removals_are_counted() -> None:
    changes = _markdown.render_diff(
        {"targets": [{"id": "old"}]},
        {"targets": [{"id": "new1"}, {"id": "new2"}]},
    )
    assert changes == (
        "### Conformance changes\n\n- 2 targets added\n- 1 target removed\n"
    )


def test_registry_changes_are_still_reported() -> None:
    def report(ref: str) -> dict[str, Any]:
        return {
            "targets": [],
            "domains": {
                "demo-conformance": {
                    "registry_repo": "open-telemetry/demo",
                    "registry_ref": ref,
                    "registry_dir": "model",
                }
            },
        }

    assert _markdown.render_diff(report("v1.0.0"), report("v1.1.0")) == (
        "### Conformance changes\n\n"
        "- registry `demo-conformance` ref `v1.0.0` → `v1.1.0`\n"
    )


def test_an_unchanged_report_has_no_diff_to_show() -> None:
    same: dict[str, Any] = {
        "targets": [{"id": TARGET, "signals": [], "findings": []}]
    }
    assert _markdown.render_diff(same, same) == ""


def test_a_finding_that_moved_everywhere_is_listed_once() -> None:
    """A new check adds the same finding to every target in one run."""
    many = _markdown._WIDESPREAD

    def report(findings: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "targets": [
                {"id": f"{TARGET}/{n}", "signals": [], "findings": findings}
                for n in range(many)
            ]
        }

    changes = _markdown.render_diff(
        report([{"id": "unit_mismatch"}]),
        report([{"id": "new_check"}, {"id": "new_check"}]),
    )
    assert (
        f"- finding `new_check` +{2 * many} across {many} targets" in changes
    )
    assert (
        f"- finding `unit_mismatch` −{many} across {many} targets" in changes
    )
    assert "<details>" not in changes
