# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""What a domain wires in when the caller brings their own registry."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Callable

import pytest

from opentelemetry.conformance import Domain, _domain
from opentelemetry.conformance._report import ClassifySpan


def classifier(model: object) -> ClassifySpan:
    del model
    return lambda span: ()


@pytest.fixture(name="domain")
def _domain_fixture(tmp_path, monkeypatch):
    """A domain whose pin can't be fetched, so a fetch fails the test."""
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / "cache"))

    def unreachable(*args: object, **kwargs: object) -> Path:
        raise AssertionError("the pinned registry was fetched")

    monkeypatch.setattr(_domain, "provision", unreachable)

    def build(
        advice_data: Callable[[Path], str] | None = None,
        config: Path | None = None,
    ) -> Domain:
        return Domain(
            name="test-conformance",
            repo="open-telemetry/semantic-conventions",
            ref="deadbeef",
            classifier=classifier,
            advice_data=advice_data,
            config=config,
        )

    return build


def test_a_caller_registry_is_used_without_fetching_the_pin(
    domain, tmp_path
) -> None:
    local = tmp_path / "working-tree" / "model"

    assert domain().weaver_defaults(local).registry == str(local)


def test_advice_data_is_read_from_the_registry_in_use(
    domain, tmp_path
) -> None:
    seen: list[Path] = []
    local = tmp_path / "working-tree" / "model"

    def advice_data(registry: Path) -> str:
        seen.append(registry)
        return str(registry / "*.json")

    defaults = domain(advice_data).weaver_defaults(local)

    assert seen == [local]
    assert defaults.advice_data == str(local / "*.json")


def signal_types(config: Path) -> list[str]:
    """The filters a merged config declares, in file order."""
    return [
        line.split("=")[1].strip().strip('"')
        for line in config.read_text().splitlines()
        if line.startswith("signal_type")
    ]


def test_a_domain_config_is_filtered_on_top_of_the_runners(
    domain, tmp_path
) -> None:
    config = tmp_path / "weaver.toml"
    config.write_text(
        "[[live-check.finding_filters]]\n"
        'signal_type = "span"\n'
        'exclude_samples = ["rpc.method"]\n'
    )

    merged = domain(config=config).weaver_config

    assert signal_types(merged) == ["resource", "span"]
    assert '"rpc.method"' in merged.read_text()


def test_a_domain_without_a_config_gets_the_runners(domain) -> None:
    assert signal_types(domain().weaver_config) == ["resource"]


def test_the_cli_names_the_command_that_was_run(
    domain, capsys: pytest.CaptureFixture[str]
) -> None:
    """A wrapper's usage line is its own console script, not the runner's."""
    with pytest.raises(SystemExit) as exit_info:
        domain().main(["--help"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.startswith("usage: test-conformance ")


def test_a_package_registry_drives_the_coverage_model(
    domain, tmp_path, monkeypatch
) -> None:
    """What the run is checked against is what its coverage is read against."""
    directory = tmp_path / "package"
    directory.mkdir()
    (directory / "conformance.yaml").write_text(
        "instrumented_library: demo\n"
        "instrumentation_library: demo-instrumentation\n"
        "weaver:\n"
        "  registry: ./model\n"
        "scenarios:\n"
        "  inference:\n"
        "    run: python inference.py\n"
    )
    resolved: list[Path] = []

    monkeypatch.setattr(_domain, "check_weaver", lambda: None)
    monkeypatch.setattr(
        _domain,
        "resolve_coverage_model",
        lambda registry, output: resolved.append(registry),
    )
    monkeypatch.setattr(_domain, "load_coverage_model", lambda path: {})

    @contextmanager
    def opened(directory: Path, **kwargs: object):
        del directory
        yield kwargs

    monkeypatch.setattr(_domain, "conformance_session", opened)

    with domain().session(directory):
        pass

    assert resolved == [directory / "model"]
