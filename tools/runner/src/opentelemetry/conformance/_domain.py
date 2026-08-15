# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""One set of semantic conventions, as everything the runner needs about it.

Wrapping the runner for a domain is the same assembly every time: fetch a
pinned registry, resolve it into a coverage model, reduce a run against that
model, and offer the result as a ``SessionFactory`` and a CLI. A
:class:`Domain` is what differs — the pin, how to recognise its span types,
and any advice policies of its own.
"""

from __future__ import annotations

import inspect
import shutil
import sys
from collections.abc import Generator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from ._model import fingerprint as model_fingerprint
from ._model import load as load_coverage_model
from ._model import resolve as resolve_coverage_model
from ._registry import cache_dir, check_weaver, provision
from ._report import ClassifySpan
from ._semconv import BuildData, semconv_coverage
from ._session import (
    ConformanceSession,
    SessionFactory,
    conformance_session,
)
from ._spec import ServerSpec, WeaverSpec

# Span invariants every domain is checked against; see policies/.
_RUNNER_POLICIES = Path(__file__).parent / "policies"
# Findings filtered out whatever the domain; see weaver-defaults.toml.
_RUNNER_CONFIG = Path(__file__).parent / "weaver-defaults.toml"

CoverageModel = Mapping[str, Any]


@dataclass(frozen=True)
class Domain:
    """A semantic-conventions domain the runner can check against."""

    # The name a directory asks for under ``runner:``, and the wrapper's
    # console script. Registered under ``opentelemetry_conformance_runners``.
    name: str
    # The GitHub repo holding the registry, and the ref to pin it at.
    repo: str
    ref: str
    # How to recognise this domain's span types. A factory rather than the
    # classifier itself, because a domain may need the resolved model to
    # decide — GenAI reads each span type's kind from it.
    classifier: Callable[[CoverageModel], ClassifySpan]

    # Where the registry sits inside the checkout.
    registry_dir: str = "model"
    # Advice policies of this domain's own, loaded on top of the runner's.
    policies: Path | None = None
    # A ``.weaver.toml`` of this domain's own, appended to the runner's.
    config: Path | None = None
    # A ``--advice-data`` glob, given the registry the run validates against.
    # A callable because some registries need patching on the way — see the
    # GenAI domain. It must not write into the registry it is given: that is
    # somebody's working tree whenever the pin has been overridden.
    advice_data: Callable[..., str] | None = None

    @cached_property
    def checkout(self) -> Path:
        """The pinned checkout, fetched if the cache hasn't got it.

        Keyed on the repo, not on this domain, so two domains pinning the same
        registry at the same ref share one checkout and one resolved model
        instead of fetching identical content twice.
        """
        return provision(
            self.repo, self.ref, label=self.repo.rpartition("/")[2]
        )

    @property
    def registry(self) -> Path:
        return self.checkout / self.registry_dir

    @cached_property
    def coverage_model(self) -> CoverageModel:
        """What the pinned registry declares. Resolved once per pin.

        Cached under its pin rather than inside the checkout, so it survives a
        re-fetch and doesn't depend on the registry being a local directory.
        """
        model = (
            cache_dir()
            / "coverage-models"
            / f"{self._pin}-{model_fingerprint()}.json"
        )
        resolve_coverage_model(self.registry, model)
        return load_coverage_model(model)

    @property
    def _pin(self) -> str:
        """Everything that decides what a resolved model holds, as a name."""
        label = self.repo.rpartition("/")[2]
        return f"{label}-{self.ref}-{self.registry_dir.replace('/', '-')}"

    @cached_property
    def advice_policies(self) -> Path:
        """The runner's policies and this domain's, in one directory.

        Weaver takes a single ``--advice-policies``, so the two sets are
        assembled into one. Rebuilt each time: the domain's move with the
        checkout, the runner's with an upgrade.
        """
        assembled = cache_dir() / "advice-policies" / self.name
        if assembled.exists():
            shutil.rmtree(assembled)
        assembled.mkdir(parents=True)
        for source in (_RUNNER_POLICIES, self.policies):
            for policy in sorted(source.glob("*.rego")) if source else ():
                shutil.copy(policy, assembled / policy.name)
        return assembled

    @cached_property
    def weaver_config(self) -> Path:
        """The runner's config and this domain's, in one file.

        Weaver takes a single ``--config``, so the two are concatenated.
        Appending rather than merging is enough because a config is filters:
        every table in either file is one more thing left out, and neither
        file overrides a key of the other's.
        """
        sources = [_RUNNER_CONFIG] + ([self.config] if self.config else [])
        assembled = cache_dir() / "weaver-config" / f"{self.name}.toml"
        assembled.parent.mkdir(parents=True, exist_ok=True)
        assembled.write_text(
            "\n".join(
                source.read_text(encoding="utf-8") for source in sources
            ),
            encoding="utf-8",
        )
        return assembled

    def weaver_defaults(
        self,
        registry: Path | None = None,
        model_path: Path | None = None,
    ) -> WeaverSpec:
        """This domain's registry and advice, as defaults for a package.

        ``registry`` is the one the run is checked against when the caller
        brought their own; the pin is then never fetched. Advice data is read
        from whichever registry that is, so a local checkout is checked
        against its own schemas rather than the pinned ones.
        """
        registry = registry if registry is not None else self.registry
        advice_data = None
        if self.advice_data:
            params = list(inspect.signature(self.advice_data).parameters.values())
            if len(params) >= 2 or any(
                p.kind == inspect.Parameter.VAR_POSITIONAL for p in params
            ):
                advice_data = self.advice_data(registry, model_path)
            else:
                advice_data = self.advice_data(registry)

        return WeaverSpec(
            registry=str(registry),
            policies=str(self.advice_policies),
            advice_data=advice_data,
            config=str(self.weaver_config),
        )

    @property
    def session(self) -> SessionFactory:
        return self._session

    @contextmanager
    def _session(
        self,
        directory: Path | str,
        *,
        report_dir: Path | str | None = None,
        data_file: Path | str | None = None,
        variables: Mapping[str, str] | None = None,
        weaver: WeaverSpec | None = None,
        server: ServerSpec | None = None,
        env: Mapping[str, str] | None = None,
        build_data: BuildData | None = None,
    ) -> Generator[ConformanceSession, None, None]:
        """A conformance session wired to this domain.

        Signature-compatible with ``conformance_session``, supplying this
        domain's wiring under whatever the caller passes. A caller's registry
        wins outright — it is validated against, reduced against and read for
        advice data, and the pin is not fetched at all. A conventions repo
        checking its working tree sees its own span types in the data file
        rather than the pinned registry's, and needs no network to do it.

        No server is wired in; a scenario that needs one declares it.
        """
        # Up front: resolving the coverage model shells out to weaver too, and
        # a missing binary should be reported here rather than from there.
        check_weaver()
        override = (
            Path(weaver.registry) if weaver and weaver.registry else None
        )
        with ExitStack() as stack:
            resolved_build_data, model_path = self._coverage(stack, override)
            if build_data is None:
                build_data = resolved_build_data
            with conformance_session(
                directory,
                report_dir=report_dir,
                data_file=data_file,
                variables=variables,
                weaver=(weaver or WeaverSpec()).over(
                    self.weaver_defaults(override, model_path)
                ),
                server=server,
                env=env,
                build_data=build_data,
            ) as session:
                yield session

    def _coverage(
        self, stack: ExitStack, override: Path | None
    ) -> tuple[BuildData, Path]:
        """Reduce a run against whichever registry it is checked against.

        The pinned one is resolved into the cache and reused. An
        overriding one is somebody's working tree, so its model is resolved
        fresh for the session and thrown away with it.
        """
        if override is None:
            model_path = (
                cache_dir()
                / "coverage-models"
                / f"{self._pin}-{model_fingerprint()}.json"
            )
            resolve_coverage_model(self.registry, model_path)
        else:
            scratch = Path(stack.enter_context(TemporaryDirectory()))
            model_path = scratch / "coverage-model.json"
            resolve_coverage_model(override, model_path)

        model = load_coverage_model(model_path)
        build_data = semconv_coverage(self.classifier(model), lambda: model)
        return build_data, model_path

    def main(self, argv: list[str] | None = None) -> int:
        """This domain's CLI: ``otel-conformance`` with the domain pinned."""
        from ._cli import main  # noqa: PLC0415  (cycle)

        return main(argv, session=self.session, prog=self.name)

    def cli(self) -> None:
        """Console-script entry point."""
        sys.exit(self.main())
