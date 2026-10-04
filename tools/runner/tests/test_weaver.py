# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Weaver 0.27 HTTP shutdown protocol."""

from unittest.mock import Mock

import pytest

from opentelemetry.conformance import _weaver


def test_end_reads_report_before_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    process = Mock()
    process.wait.return_value = 0
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._stopped = False
    weaver._admin_port = 1234
    weaver._process = process

    def post(url: str, *, timeout: int) -> Mock:
        calls.append(url.rsplit("/", 1)[-1])
        assert timeout == 15
        return Mock()

    def get(url: str, *, timeout: int) -> Mock:
        calls.append(url.rsplit("/", 1)[-1])
        assert timeout == 15
        return Mock(json=lambda: {"samples": []})

    monkeypatch.setattr(_weaver, "post", post)
    monkeypatch.setattr(_weaver, "get", get)

    report = weaver.end(timeout=15)

    assert report["samples"] == []
    assert calls == ["stop", "report", "shutdown"]
    process.wait.assert_called_once_with(timeout=15)


def test_shutdown_follows_report_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._admin_port = 1234
    weaver._process = Mock()
    monkeypatch.setattr(weaver, "_read_weaver_logs", lambda: "")

    def post(url: str, *, timeout: int) -> Mock:
        calls.append(url.rsplit("/", 1)[-1])
        return Mock()

    def get(url: str, *, timeout: int) -> Mock:
        calls.append(url.rsplit("/", 1)[-1])
        response = Mock()
        response.raise_for_status.side_effect = RuntimeError("report failed")
        return response

    monkeypatch.setattr(_weaver, "post", post)
    monkeypatch.setattr(_weaver, "get", get)

    with pytest.raises(RuntimeError, match="report failed"):
        weaver._do_stop(timeout=15)

    assert calls == ["stop", "report", "shutdown"]
