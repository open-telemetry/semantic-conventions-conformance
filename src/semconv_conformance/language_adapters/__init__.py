# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Per-language scenario adapter scaffolding for conformance domains.

Each language lives in its own module (e.g. `python.py`, `java.py`) and
exports a `build_adapter(ctx)` free function; the `DomainLanguageAdapters`
dispatcher wires them into a registry keyed by language slug.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from semconv_conformance.locations import ScenarioLocation

from . import python
from ._common import (
    AdapterContext,
    CommandResult,
    LanguageAdapter,
    UvNotInstalledError,
)

__all__ = [
    "CommandResult",
    "DomainLanguageAdapters",
    "LanguageAdapter",
    "UvNotInstalledError",
]


#: Adapter builders keyed by language slug. Languages are added here as their
#: scenarios land; the slug must also have an entry in ``languages.json``.
_BUILDERS: dict[str, Callable[[AdapterContext], LanguageAdapter]] = {
    "python": python.build_adapter,
}


class DomainLanguageAdapters:
    """Build the language adapter registry for one conformance domain."""

    def __init__(
        self,
        *,
        domain_dir: Path,
        supported_languages: Iterable[str],
    ) -> None:
        self._ctx = AdapterContext(domain_dir=domain_dir)
        self.by_language: dict[str, LanguageAdapter] = {}
        for language in supported_languages:
            builder = _BUILDERS.get(language)
            if builder is None:
                raise ValueError(f"Unsupported language adapter: {language}")
            self.by_language[language] = builder(self._ctx)

    def get(self, language: str) -> LanguageAdapter | None:
        """Return the adapter for `language`, or None if unsupported."""
        return self.by_language.get(language)

    def install_with_uv(self, *install_args: str, label: str) -> None:
        """Install a Python package into the current interpreter via uv."""
        python.install_with_uv(self._ctx.domain_dir, *install_args, label=label)

    def run_scenario_cmd(self, location: ScenarioLocation, env: dict[str, str]) -> CommandResult:
        """Run the scenario command."""
        adapter = self.by_language.get(location.lang)
        if adapter is None:
            return CommandResult(False, 0)
        return adapter.run_scenario(location.library, location.ecosystem, env)

    def list_available_scenarios(self) -> list[str]:
        """Discover all available scenario ids."""
        scenarios: list[str] = []
        for adapter in self.by_language.values():
            scenarios.extend(adapter.list_scenarios())
        return scenarios
