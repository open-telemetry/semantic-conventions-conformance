# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Declaring a registry as a git URL rather than as a path on disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from opentelemetry.conformance import _registry
from opentelemetry.conformance._registry import (
    local_registry,
    parse_git_registry,
)

_URL = "https://github.com/open-telemetry/semantic-conventions-genai.git"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (f"{_URL}@67dff024[model]", (_URL, "67dff024", "model")),
        (f"{_URL}@main", (_URL, "main", None)),
        (f"{_URL}[model]", (_URL, None, "model")),
        (_URL, (_URL, None, None)),
    ],
)
def test_a_git_url_is_read_as_url_ref_and_sub_folder(
    value: str, expected: tuple[str, str | None, str | None]
) -> None:
    declared = parse_git_registry(value)

    assert declared is not None
    assert (declared.url, declared.ref, declared.sub_folder) == expected


@pytest.mark.parametrize(
    "value",
    [
        "/checkout/model",
        "../model",
        "${ROOT}/model",
        "https://example.com/registry.zip[model]",
        # A checkout that happens to be named like a URL's tail.
        "../semantic-conventions-genai.git",
    ],
)
def test_anything_that_is_not_a_git_url_stays_a_path(value: str) -> None:
    assert parse_git_registry(value) is None
    assert local_registry(value) == Path(value)


def test_a_git_url_is_fetched_once_into_the_cache(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / "cache"))
    fetched: list[str] = []

    def extract(url: str, target: Path, *, label: str) -> None:
        del label
        fetched.append(url)
        (target / "model").mkdir(parents=True)

    monkeypatch.setattr(_registry, "_download_and_extract", extract)

    registry = local_registry(f"{_URL}@67dff024[model]")

    assert registry == (
        tmp_path / "cache" / "semantic-conventions-genai-67dff024" / "model"
    )
    assert registry.is_dir()
    assert local_registry(f"{_URL}@67dff024[model]") == registry
    assert fetched == [
        "https://github.com/open-telemetry/semantic-conventions-genai"
        "/archive/67dff024.tar.gz"
    ]


def test_a_ref_stays_one_directory_in_the_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / "cache"))

    def extract(url: str, target: Path, *, label: str) -> None:
        del url, label
        target.mkdir(parents=True)

    monkeypatch.setattr(_registry, "_download_and_extract", extract)

    registry = local_registry(f"{_URL}@release/../../v1.0")

    assert registry.parent == tmp_path / "cache"


def test_a_url_that_is_not_on_github_says_so(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SEMCONV_CACHE", str(tmp_path / "cache"))

    with pytest.raises(RuntimeError, match="only github.com"):
        local_registry("https://gitlab.com/org/registry.git@main[model]")
