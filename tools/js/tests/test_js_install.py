# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The one Node step a conformance.yaml cannot name portably."""

from __future__ import annotations

from pathlib import Path

import pytest

import otel_conformance_js
from otel_conformance_js import (
    BUILD_MARKER,
    LayoutError,
    build_root,
    npm_command,
    playwright_command,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / BUILD_MARKER).write_text("", encoding="utf-8")
    return tmp_path


class TestFindingTheBuild:
    def test_it_is_found_from_a_scenario_directory(self, root: Path) -> None:
        """How deep a scenario sits is the layout's business, not its own."""
        scenario = root / "express" / "opentelemetry-express" / "server"
        scenario.mkdir(parents=True)

        assert build_root(scenario) == root

    def test_the_build_root_itself_counts(self, root: Path) -> None:
        assert build_root(root) == root

    def test_being_outside_a_build_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LayoutError, match=BUILD_MARKER):
            build_root(tmp_path)


class TestInstalling:
    def test_missing_build_root_is_reported(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        message = "no Node conformance build here"

        def fail_to_find_build() -> Path:
            raise LayoutError(message)

        monkeypatch.setattr(
            otel_conformance_js, "build_root", fail_to_find_build
        )

        assert otel_conformance_js.main(["install"]) == 1
        assert capsys.readouterr().err == f"{message}\n"

    def test_it_installs_from_the_committed_lockfile(self) -> None:
        """`ci`, not `install`: a run measures the pinned versions."""
        assert npm_command()[-1] == "ci"

    def test_npm_is_found_the_way_a_shell_would_find_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Windows npm is a `.cmd`, which a direct spawn would not find."""
        monkeypatch.setattr(
            otel_conformance_js.shutil,
            "which",
            lambda name: f"C:/node/{name}.cmd",
        )

        assert npm_command()[0] == "C:/node/npm.cmd"

    def test_it_installs_the_whole_build_rather_than_one_scenario(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[list[str], Path]] = []
        monkeypatch.setattr(otel_conformance_js, "build_root", lambda: root)
        monkeypatch.setattr(
            otel_conformance_js.subprocess,
            "call",
            lambda command, cwd: calls.append((command, cwd)) or 0,
        )

        assert otel_conformance_js.main(["install"]) == 0
        assert calls[0][1] == root

    def test_it_installs_the_pinned_browser_after_the_workspace(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[list[str], Path]] = []
        monkeypatch.setattr(otel_conformance_js, "build_root", lambda: root)
        monkeypatch.setattr(
            otel_conformance_js.subprocess,
            "call",
            lambda command, cwd: calls.append((command, cwd)) or 0,
        )

        assert otel_conformance_js.main(["install", "--browser", "chromium"]) == 0
        assert calls == [
            (npm_command(), root),
            (playwright_command(root, "chromium"), root),
        ]

    def test_a_missing_browser_executable_is_reported(
        self,
        root: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        def call(command: list[str], cwd: Path) -> int:
            assert cwd == root
            if command == npm_command():
                return 0
            raise FileNotFoundError(2, "No such file or directory", command[0])

        monkeypatch.setattr(otel_conformance_js, "build_root", lambda: root)
        monkeypatch.setattr(otel_conformance_js.subprocess, "call", call)
        monkeypatch.setattr(
            otel_conformance_js.shutil,
            "which",
            lambda name: None if name == "node" else f"/usr/bin/{name}",
        )

        assert otel_conformance_js.main(["install", "--browser", "chromium"]) == 1
        assert (
            capsys.readouterr().err
            == "node is not available, and a Node scenario requires it\n"
        )

    def test_linux_installs_the_browser_system_dependencies(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(otel_conformance_js.sys, "platform", "linux")

        assert playwright_command(root, "chromium")[-2:] == [
            "--with-deps",
            "chromium",
        ]
