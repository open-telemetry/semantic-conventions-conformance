# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Which wrapper opens a conformance directory.

The runner carries no semantic conventions, so a directory has to say which
registry and reduction it wants checking against. It names a wrapper::

    runner: genai-conformance

and that name is registered by the wrapper package itself, under the
``opentelemetry_conformance_runners`` entry-point group. Installing the
package is what makes the name resolvable; the value is the same string as
the wrapper's console script, so what a file says is what you would type.
"""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points
from pathlib import Path
from typing import TYPE_CHECKING

from ._spec import SpecError, declared_runner

if TYPE_CHECKING:
    from ._domain import Domain
    from ._session import SessionFactory

GROUP = "opentelemetry_conformance_runners"


def installed() -> dict[str, str]:
    """Every registered wrapper name, mapped to what provides it."""
    return {
        entry.name: entry.value for entry in entry_points(group=GROUP)
    }


def resolve(directory: Path) -> SessionFactory:
    """The session factory for ``directory``.

    A directory naming no runner gets the plain session — enough to run
    scenarios against a registry passed on the command line, which is how the
    runner is used without any wrapper at all.
    """
    from ._session import conformance_session  # noqa: PLC0415  (cycle)

    name = declared_runner(directory)
    if name is None:
        return conformance_session
    return load(name)


def load(name: str) -> SessionFactory:
    """The session factory registered under ``name``."""
    for entry in entry_points(group=GROUP):
        if entry.name == name:
            return entry.load()

    known = sorted(installed())
    raise SpecError(
        f"no conformance runner named {name!r} is installed"
        + (
            f" — installed: {', '.join(known)}"
            if known
            else " — none are installed; `pip install -e tools/<domain>/runner`"
        )
    )


def domain(name: str) -> Domain | None:
    """The :class:`Domain` a wrapper is built from, if it has one.

    :func:`load` gives back a session factory, which is all running a scenario
    needs. Reading what a registry declares, or which pin it resolved at,
    needs the domain behind it — and opening a session to reach one would
    fetch a registry and start weaver to answer a question about neither.

    ``None`` means the wrapper is assembled some other way; an unknown name
    still raises from :func:`load`.
    """
    from ._domain import Domain as _Domain  # noqa: PLC0415  (cycle)

    for entry in entry_points(group=GROUP):
        if entry.name == name:
            found = getattr(import_module(entry.module), "DOMAIN", None)
            return found if isinstance(found, _Domain) else None

    load(name)  # raises, saying which names are installed
    return None
