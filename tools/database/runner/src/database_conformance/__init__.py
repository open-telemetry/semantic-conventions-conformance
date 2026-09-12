# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance runs against the database semantic conventions."""

import sys
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from pathlib import Path

from opentelemetry.conformance import (
    ConformanceSession,
    Domain,
    PackageSpec,
    ServerSpec,
    SpecError,
    WeaverSpec,
    load_spec,
    main,
    require_pin,
)

from ._container import DatabaseContainer
from ._coverage import classifier, classify_span
from ._mariadb import MariaDB
from ._postgres import Postgres
from ._sql_server import SQLServer

_HERE = Path(__file__).parent

DOMAIN = Domain(
    name="database-conformance",
    repo="open-telemetry/semantic-conventions",
    ref=require_pin(_HERE / "versions.env", "SEMCONV_REF"),
    classifier=classifier,
)

_BACKENDS: dict[str, Callable[[], DatabaseContainer]] = {
    "mariadb": MariaDB,
    "postgresql": Postgres,
    "sql_server": SQLServer,
}


def _backend_name(spec: PackageSpec) -> str:
    where = f"{spec.directory / 'conformance.yaml'}.runner_config"
    config = spec.runner_config
    if set(config) != {"backend"}:
        raise SpecError(
            f"{where} must contain exactly one string key named 'backend'"
        )
    backend = config["backend"]
    if not isinstance(backend, str):
        raise SpecError(
            f"{where}.backend: expected a string"
        )
    if backend not in _BACKENDS:
        choices = ", ".join(sorted(_BACKENDS))
        raise SpecError(
            f"{where}.backend selects unsupported backend {backend!r}; "
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
    spec: PackageSpec | None = None,
) -> Generator[ConformanceSession, None, None]:
    """Open a database conformance session with its configured backend."""
    spec = spec or load_spec(Path(directory))
    with _BACKENDS[_backend_name(spec)]() as backend:
        resolved = dict(variables or {})
        resolved.update(backend.variables)
        session_context = DOMAIN.session(
            directory,
            report_dir=report_dir,
            data_file=data_file,
            variables=resolved,
            weaver=weaver,
            server=server,
            env=env,
            spec=spec,
            **({"build_data": build_data} if build_data is not None else {}),
        )
        with session_context as session:
            yield session


def cli() -> None:
    """Run the database conformance CLI."""
    sys.exit(main(session=database_session, prog=DOMAIN.name))


__all__ = ["DOMAIN", "classify_span", "cli", "database_session"]
