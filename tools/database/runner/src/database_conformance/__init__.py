# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance runs against the database semantic conventions."""

import sys
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import yaml

from opentelemetry.conformance import (
    ConformanceSession,
    Domain,
    PackageSpec,
    ServerSpec,
    SpecError,
    WeaverSpec,
    main,
    require_pin,
)

from ._container import DatabaseContainer
from ._coverage import classifier, classify_span
from ._mariadb import MariaDB
from ._opensearch import OpenSearch
from ._postgres import Postgres

_HERE = Path(__file__).parent

DOMAIN = Domain(
    name="database-conformance",
    repo="open-telemetry/semantic-conventions",
    ref=require_pin(_HERE / "versions.env", "SEMCONV_REF"),
    classifier=classifier,
)

_BACKENDS: dict[str, Callable[[], DatabaseContainer]] = {
    "mariadb": MariaDB,
    "opensearch": OpenSearch,
    "postgresql": Postgres,
}


def _backend_name(directory: Path | str) -> str:
    path = Path(directory) / "database.yaml"
    try:
        parsed = cast(object, yaml.safe_load(path.read_text(encoding="utf-8")))
    except OSError as error:
        raise SpecError(f"cannot read {path}: {error}") from error
    except yaml.YAMLError as error:
        raise SpecError(f"cannot parse {path}: {error}") from error
    if not isinstance(parsed, Mapping):
        raise SpecError(
            f"{path} must contain exactly one string key named 'backend'"
        )
    config = cast(Mapping[object, object], parsed)
    if len(config) != 1 or "backend" not in config:
        raise SpecError(
            f"{path} must contain exactly one string key named 'backend'"
        )
    backend = config["backend"]
    if not isinstance(backend, str):
        raise SpecError(
            f"{path} must contain exactly one string key named 'backend'"
        )
    if backend not in _BACKENDS:
        choices = ", ".join(sorted(_BACKENDS))
        raise SpecError(
            f"{path} selects unsupported backend {backend!r}; "
            f"expected one of: {choices}"
        )
    return backend


@contextmanager
def database_session(
    directory: Path | str,
    *,
    report_dir: Path | str | None = None,
    data_file: Path | str | None = None,
    variables: Mapping[str, str] | None = None,
    weaver: WeaverSpec | None = None,
    server: ServerSpec | None = None,
    env: Mapping[str, str] | None = None,
    build_data: Callable[[Path, PackageSpec], object] | None = None,
) -> Generator[ConformanceSession, None, None]:
    """Open a database conformance session with its configured backend."""
    with _BACKENDS[_backend_name(directory)]() as backend:
        resolved = dict(variables or {})
        resolved.update(backend.variables)
        if build_data is None:
            session_context = DOMAIN.session(
                directory,
                report_dir=report_dir,
                data_file=data_file,
                variables=resolved,
                weaver=weaver,
                server=server,
                env=env,
            )
        else:
            session_context = DOMAIN.session(
                directory,
                report_dir=report_dir,
                data_file=data_file,
                variables=resolved,
                weaver=weaver,
                server=server,
                env=env,
                build_data=build_data,
            )
        with session_context as session:
            yield session


def cli() -> None:
    """Run the database conformance CLI."""
    sys.exit(main(session=database_session, prog=DOMAIN.name))


__all__ = ["DOMAIN", "classify_span", "cli", "database_session"]
