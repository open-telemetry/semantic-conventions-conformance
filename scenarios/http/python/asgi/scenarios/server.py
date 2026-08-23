# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A bare ASGI workload, with no instrumentation attached."""

from __future__ import annotations

from otel_http_test_client import CONTENT_TYPE, respond


async def application(scope, receive, send) -> None:
    if scope["type"] != "http":
        return

    chunks = []
    more_body = True
    while more_body:
        message = await receive()
        chunks.append(message.get("body", b""))
        more_body = message.get("more_body", False)
    body = b"".join(chunks).decode() or None
    status, payload = respond(scope["method"], scope["path"], body)
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", CONTENT_TYPE.encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": payload.encode()})
