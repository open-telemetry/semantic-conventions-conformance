# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import otel_conformance_ruby
from otel_conformance_ruby import (
    BUNDLE_DIRECTORY,
    GEMFILE,
    LOCKFILE,
    LayoutError,
    ToolError,
    bundle_command,
    bundle_environment,
    package_root,
    run_command,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / GEMFILE).write_text("", encoding="utf-8")
    (tmp_path / LOCKFILE).write_text("", encoding="utf-8")
    return tmp_path


@pytest.fixture
def scenario(root: Path) -> Path:
    directory = root / "net-http" / "client"
    directory.mkdir(parents=True)
    (directory / "client.rb").write_text("", encoding="utf-8")
    return directory


@pytest.fixture
def tools(monkeypatch: pytest.MonkeyPatch) -> None:
    paths = {
        "ruby": "C:/Ruby/bin/ruby.exe",
        "bundle": "C:/Ruby/bin/bundle.cmd",
    }
    monkeypatch.setattr(otel_conformance_ruby.shutil, "which", paths.get)


class TestFindingThePackage:
    def test_it_is_found_from_a_nested_scenario(
        self, root: Path, scenario: Path
    ) -> None:
        assert package_root(scenario) == root

    def test_the_nearest_package_wins(
        self, root: Path, scenario: Path
    ) -> None:
        (scenario / GEMFILE).write_text("", encoding="utf-8")
        (scenario / LOCKFILE).write_text("", encoding="utf-8")

        assert package_root(scenario) == scenario

    @pytest.mark.parametrize(
        "present, missing", [(GEMFILE, LOCKFILE), (LOCKFILE, GEMFILE)]
    )
    def test_an_incomplete_package_says_what_is_missing(
        self, tmp_path: Path, present: str, missing: str
    ) -> None:
        (tmp_path / present).write_text("", encoding="utf-8")

        with pytest.raises(LayoutError, match=missing):
            package_root(tmp_path)

    def test_being_outside_a_package_says_so(self, tmp_path: Path) -> None:
        with pytest.raises(LayoutError, match=LOCKFILE):
            package_root(tmp_path)


class TestCommands:
    def test_bundler_is_started_portably_on_windows(self, tools: None) -> None:
        assert bundle_command("install") == [
            "C:/Ruby/bin/ruby.exe",
            "-S",
            "bundle",
            "install",
        ]

    def test_run_uses_the_same_ruby_inside_bundler(
        self, tools: None, root: Path
    ) -> None:
        entry = root / "server.rb"

        assert run_command(entry, ["--port", "8080"]) == [
            "C:/Ruby/bin/ruby.exe",
            "-S",
            "bundle",
            "exec",
            "C:/Ruby/bin/ruby.exe",
            str(entry),
            "--port",
            "8080",
        ]

    @pytest.mark.parametrize("missing", ["ruby", "bundle"])
    def test_missing_tools_are_reported(
        self, monkeypatch: pytest.MonkeyPatch, missing: str
    ) -> None:
        monkeypatch.setattr(
            otel_conformance_ruby.shutil,
            "which",
            lambda name: None if name == missing else f"/usr/bin/{name}",
        )

        with pytest.raises(ToolError, match=missing):
            bundle_command("install")


def test_the_bundle_is_frozen_and_repository_local(root: Path) -> None:
    environment = bundle_environment(
        root,
        {
            "KEEP": "yes",
            "BUNDLE_DISABLE_SHARED_GEMS": "true",
            "BUNDLE_PATH": "somewhere-else",
            "GEM_HOME": "user-gems",
            "GEM_PATH": "shared-gems",
        },
    )

    assert environment == {
        "KEEP": "yes",
        "BUNDLE_DISABLE_SHARED_GEMS": "true",
        "BUNDLE_FROZEN": "true",
        "BUNDLE_GEMFILE": str(root / GEMFILE),
        "BUNDLE_IGNORE_CONFIG": "true",
        "BUNDLE_PATH": str(root / BUNDLE_DIRECTORY),
    }


class TestTheCommandLine:
    @pytest.fixture
    def calls(
        self,
        scenario: Path,
        tools: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        monkeypatch.chdir(scenario)

        def call(command: list[str], *, cwd: Path, env: dict[str, str]) -> int:
            calls.append({"command": command, "cwd": cwd, "env": env})
            return 0

        monkeypatch.setattr(otel_conformance_ruby.subprocess, "call", call)
        return calls

    def test_install_uses_the_lock_from_the_package_root(
        self, root: Path, calls: list[dict[str, Any]]
    ) -> None:
        assert otel_conformance_ruby.main(["install"]) == 0

        assert calls[0]["command"][-1:] == ["install"]
        assert calls[0]["cwd"] == root
        assert calls[0]["env"]["BUNDLE_GEMFILE"] == str(root / GEMFILE)
        assert calls[0]["env"]["BUNDLE_PATH"] == str(root / BUNDLE_DIRECTORY)

    def test_run_resolves_the_entry_before_using_the_package_cwd(
        self, root: Path, scenario: Path, calls: list[dict[str, Any]]
    ) -> None:
        assert (
            otel_conformance_ruby.main(["run", "client.rb", "--port", "8080"])
            == 0
        )

        assert calls[0]["cwd"] == root
        assert calls[0]["command"][-3:] == [
            str(scenario / "client.rb"),
            "--port",
            "8080",
        ]
        assert calls[0]["env"]["BUNDLE_FROZEN"] == "true"

    def test_a_failed_child_status_is_returned(
        self,
        scenario: Path,
        tools: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(scenario)
        monkeypatch.setattr(
            otel_conformance_ruby.subprocess,
            "call",
            lambda command, *, cwd, env: 23,
        )

        assert otel_conformance_ruby.main(["install"]) == 23

    def test_missing_layout_is_a_clear_cli_error(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)

        assert otel_conformance_ruby.main(["install"]) == 1
        assert LOCKFILE in capsys.readouterr().err

    def test_missing_entry_is_a_clear_cli_error(
        self,
        scenario: Path,
        tools: None,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(scenario)

        assert otel_conformance_ruby.main(["run", "missing.rb"]) == 1
        assert "entry point does not exist" in capsys.readouterr().err

    def test_missing_tool_is_a_clear_cli_error(
        self,
        scenario: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(scenario)
        monkeypatch.setattr(
            otel_conformance_ruby.shutil, "which", lambda name: None
        )

        assert otel_conformance_ruby.main(["install"]) == 1
        assert "ruby is not on PATH" in capsys.readouterr().err
