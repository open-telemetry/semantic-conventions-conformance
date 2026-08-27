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
    WeaverSpec,
    main,
    require_pin,
)

from ._coverage import classifier, classify_span
from ._postgres import Postgres

_HERE = Path(__file__).parent

DOMAIN = Domain(
    name="database-conformance",
    repo="open-telemetry/semantic-conventions",
    ref=require_pin(_HERE / "versions.env", "SEMCONV_REF"),
    classifier=classifier,
)

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
    """Open a database conformance session backed by PostgreSQL."""
    with Postgres() as postgres:
        resolved = dict(variables or {})
        resolved.update(postgres.variables)
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
    """Run the database CLI with its PostgreSQL-backed session."""
    sys.exit(main(session=database_session, prog=DOMAIN.name))

__all__ = ["DOMAIN", "classify_span", "cli", "database_session"]
