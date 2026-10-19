# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Weaver HTTP shutdown protocols."""

from unittest.mock import Mock

import pytest

pytest.importorskip("opentelemetry.test.weaver_live_check")

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
        return Mock(json=lambda: {"state": "stopped", "report": True})

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


@pytest.mark.parametrize("samples", [[], [{"span": {"name": "example"}}]])
def test_end_reads_legacy_stop_report(
    samples: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    process = Mock()
    process.wait.return_value = 0
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._stopped = False
    weaver._admin_port = 1234
    weaver._process = process
    post = Mock(
        return_value=Mock(json=lambda: {"samples": samples, "statistics": {}})
    )
    get = Mock()
    monkeypatch.setattr(_weaver, "post", post)
    monkeypatch.setattr(_weaver, "get", get)

    report = weaver.end(timeout=15)

    assert report["samples"] == samples
    assert report["statistics"] == {}
    post.assert_called_once_with("http://localhost:1234/stop", timeout=15)
    get.assert_not_called()
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
        return Mock(json=lambda: {"state": "stopped", "report": True})

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


def test_shutdown_follows_missing_report(monkeypatch: pytest.MonkeyPatch) -> None:
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._admin_port = 1234
    weaver._process = Mock()
    monkeypatch.setattr(weaver, "_read_weaver_logs", lambda: "")
    post = Mock(
        return_value=Mock(json=lambda: {"state": "stopped", "report": False})
    )
    get = Mock()
    monkeypatch.setattr(_weaver, "post", post)
    monkeypatch.setattr(_weaver, "get", get)

    with pytest.raises(RuntimeError, match="stopped without an HTTP report"):
        weaver._do_stop(timeout=15)

    assert [call.args[0] for call in post.call_args_list] == [
        "http://localhost:1234/stop",
        "http://localhost:1234/shutdown",
    ]
    get.assert_not_called()
    weaver._process.wait.assert_not_called()


@pytest.mark.parametrize("response", [None, [], {}, {"samples": []}])
def test_unexpected_stop_response_is_reported(
    response: object,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._admin_port = 1234
    weaver._process = Mock()
    monkeypatch.setattr(weaver, "_read_weaver_logs", lambda: "weaver log")
    monkeypatch.setattr(_weaver, "post", Mock(return_value=Mock(json=lambda: response)))
    get = Mock()
    monkeypatch.setattr(_weaver, "get", get)

    with pytest.raises(RuntimeError, match="Unexpected Weaver /stop response"):
        weaver._do_stop(timeout=15)

    get.assert_not_called()
    weaver._process.wait.assert_not_called()
    assert "Unexpected Weaver /stop response" in caplog.text
    assert "weaver log" in caplog.text
