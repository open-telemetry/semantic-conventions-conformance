# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Which wrapper opens a directory."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from opentelemetry.conformance import _runners
from opentelemetry.conformance._domain import Domain
from opentelemetry.conformance._session import conformance_session
from opentelemetry.conformance._spec import SpecError

MINIMAL = """
instrumented_library: demo
instrumentation_library: demo-instrumentation
scenarios:
  one:
    run: true
"""


def write(directory: Path, spec: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "conformance.yaml").write_text(spec)
    return directory


class _Entry:
    def __init__(self, name: str, factory: object) -> None:
        self.name = name
        self.value = f"test:{name}"
        self.module = name
        self._factory = factory

    def load(self) -> object:
        return self._factory


@pytest.fixture(name="registered")
def _registered(monkeypatch):
    """Register wrappers under the entry-point group, without installing any."""

    def register(**factories: object):
        entries = [_Entry(name, f) for name, f in factories.items()]
        monkeypatch.setattr(
            _runners, "entry_points", lambda group: entries if group else []
        )

    return register


@pytest.fixture(name="exporting")
def _exporting(monkeypatch):
    """Say what each wrapper's module exports, without importing one."""

    def export(**modules: object):
        monkeypatch.setattr(
            _runners, "import_module", lambda name: modules[name]
        )

    return export


def test_a_directory_naming_no_runner_gets_the_plain_session(
    tmp_path, registered
) -> None:
    registered()

    assert _runners.resolve(write(tmp_path, MINIMAL)) is conformance_session


def test_a_directory_names_the_wrapper_that_opens_it(
    tmp_path, registered
) -> None:
    wrapper = object()
    registered(**{"demo-conformance": wrapper})

    directory = write(tmp_path, "runner: demo-conformance\n" + MINIMAL)

    assert _runners.resolve(directory) is wrapper


def test_an_uninstalled_runner_says_what_is_installed(
    tmp_path, registered
) -> None:
    registered(**{"demo-conformance": object()})

    directory = write(tmp_path, "runner: absent-conformance\n" + MINIMAL)

    with pytest.raises(SpecError, match="installed: demo-conformance"):
        _runners.resolve(directory)


def test_with_nothing_installed_it_says_how_to_install_one(
    tmp_path, registered
) -> None:
    registered()

    directory = write(tmp_path, "runner: absent-conformance\n" + MINIMAL)

    with pytest.raises(SpecError, match="none are installed"):
        _runners.resolve(directory)


def test_the_runner_is_read_without_validating_the_rest(
    tmp_path, registered
) -> None:
    """A package with no registry doesn't load, and its wrapper is what
    supplies one — so the name has to be readable before the file parses."""
    wrapper = object()
    registered(**{"demo-conformance": wrapper})

    directory = write(tmp_path, "runner: demo-conformance\n")

    assert _runners.resolve(directory) is wrapper


def test_a_directory_with_no_spec_file_says_so(tmp_path) -> None:
    with pytest.raises(SpecError, match="not found"):
        _runners.resolve(tmp_path)


def test_a_wrapper_gives_up_the_domain_it_is_built_from(
    registered, exporting
) -> None:
    demo = Domain(
        name="demo-conformance",
        repo="open-telemetry/demo",
        ref="v1.0.0",
        classifier=lambda model: lambda name, kind, attributes: set(),
    )
    registered(**{"demo-conformance": object()})
    exporting(**{"demo-conformance": SimpleNamespace(DOMAIN=demo)})

    assert _runners.domain("demo-conformance") is demo


def test_a_wrapper_assembled_some_other_way_has_no_domain(
    registered, exporting
) -> None:
    """No ``DOMAIN`` is an answer, not a failure — the name still resolved."""
    registered(**{"demo-conformance": object()})
    exporting(**{"demo-conformance": SimpleNamespace()})

    assert _runners.domain("demo-conformance") is None


def test_an_unknown_name_raises_rather_than_having_no_domain(
    registered,
) -> None:
    registered(**{"demo-conformance": object()})

    with pytest.raises(SpecError, match="installed: demo-conformance"):
        _runners.domain("absent-conformance")
