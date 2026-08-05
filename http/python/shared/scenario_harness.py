# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Server-side conformance scenario harness.

Most HTTP server scenarios share the same shape: bring up the SDK, spin up
the app in a daemon thread, drive the standard client scenarios against it,
then tear everything down. These helpers collapse that boilerplate so each
scenario's ``main()`` is a single call.

Semantic-convention opt-in environment variables are deliberately *not* set
here. A scenario that needs one declares it in its ``metadata.json`` under
``opt_in_env_vars`` and the runner exports it, so the committed data records
which instrumentations still require an opt-in and which emit stable
conventions on their own.

``app_factory`` is a zero-arg callable so the SDK is initialized before
the instrumentor runs at app-construction time.
"""

import threading
from collections.abc import Callable
from typing import Any

from http_conformance_client import run_standard_scenarios, wait_for_health
from otel_setup import flush_and_shutdown, setup_otel

BASE_HOST = "127.0.0.1"


def serve_via_wsgiref(app_factory: Callable[[], Any], port: int) -> None:
    """Run a WSGI conformance scenario against ``app_factory()``."""
    from wsgiref.simple_server import make_server

    tp, lp, mp = setup_otel()
    try:
        server = make_server(BASE_HOST, port, app_factory())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://{BASE_HOST}:{port}"
            wait_for_health(base_url)
            run_standard_scenarios(base_url)
        finally:
            server.shutdown()
            thread.join(timeout=5)
    finally:
        flush_and_shutdown(tp, lp, mp)


def serve_via_uvicorn(app_factory: Callable[[], Any], port: int) -> None:
    """Run an ASGI conformance scenario via uvicorn."""
    import uvicorn

    tp, lp, mp = setup_otel()
    try:
        server = uvicorn.Server(
            uvicorn.Config(
                app_factory(),
                host=BASE_HOST,
                port=port,
                log_level="warning",
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            base_url = f"http://{BASE_HOST}:{port}"
            wait_for_health(base_url)
            run_standard_scenarios(base_url)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
    finally:
        flush_and_shutdown(tp, lp, mp)
