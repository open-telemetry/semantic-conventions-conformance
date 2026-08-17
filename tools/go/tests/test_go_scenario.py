# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The Go toolchain a scenario directory no longer has to restate."""

from __future__ import annotations

import os
from pathlib import Path

import otel_conformance_go
import pytest
from otel_conformance_go import (
    MODULE_MARKER,
    LayoutError,
    binary,
    build_command,
    module_root,
    run_command,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / MODULE_MARKER).write_text("", encoding="utf-8")
    return tmp_path


class TestFindingTheModule:
    def test_it_is_found_from_a_scenario_directory(self, root: Path) -> None:
        """How deep a scenario sits is the layout's business, not its own."""
        scenario = root / "net-http" / "otelhttp" / "server"
        scenario.mkdir(parents=True)

        assert module_root(scenario) == root

    def test_the_module_root_itself_counts(self, root: Path) -> None:
        assert module_root(root) == root

    def test_being_outside_a_module_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LayoutError, match=MODULE_MARKER):
            module_root(tmp_path)


class TestBuilding:
    def test_it_builds_the_package_in_the_scenario_directory(
        self, root: Path
    ) -> None:
        """A scenario's package is its directory, so there is nothing to name."""
        assert build_command(root)[-1] == "."

    def test_it_names_where_the_binary_goes(self, root: Path) -> None:
        command = build_command(root)

        assert command[command.index("-o") + 1] == str(binary(root))


class TestRunning:
    def test_the_binary_is_named_absolutely(self, root: Path) -> None:
        """Windows resolves a relative command against the caller's directory,
        not the working directory a child is given.
        """
        assert Path(run_command(root)[0]).is_absolute()

    def test_it_carries_the_platforms_executable_suffix(
        self, root: Path
    ) -> None:
        expected = ".exe" if os.name == "nt" else ""

        assert binary(root).name == f"scenario{expected}"

    def test_two_scenarios_do_not_share_a_binary(self, root: Path) -> None:
        client = root / "otelhttp" / "client"
        server = root / "otelhttp" / "server"

        assert binary(client) != binary(server)

    def test_arguments_reach_the_scenario(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Through `main`, because it is the parser a leading `-` trips up."""
        commands: list[list[str]] = []
        monkeypatch.chdir(root)
        monkeypatch.setattr(
            otel_conformance_go.subprocess,
            "call",
            lambda command: commands.append(command) or 0,
        )

        assert otel_conformance_go.main(["run", "--flag", "value"]) == 0
        assert commands[0][1:] == ["--flag", "value"]

    def test_running_executes_what_building_produced(
        self, root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        commands: list[list[str]] = []
        monkeypatch.chdir(root)
        monkeypatch.setattr(
            otel_conformance_go.subprocess,
            "call",
            lambda command: commands.append(command) or 0,
        )

        assert otel_conformance_go.main(["build"]) == 0
        assert otel_conformance_go.main(["run"]) == 0
        assert commands[0][commands[0].index("-o") + 1] == commands[1][0]
