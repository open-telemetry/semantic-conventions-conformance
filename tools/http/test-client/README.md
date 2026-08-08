# HTTP conformance test client

The requests every HTTP conformance scenario makes, shared so the coverage a
client and a server produce is comparable — the same requests against the same
routes.

A **server** scenario is its routes plus one call:

```python
from otel_http_test_client import serve_and_drive

def create_app():
    ...

serve_and_drive(create_app)
```

A **client** scenario hands over its own library, and the runner starts
[`http-mock-server`](../mock-server) for it to call:

```python
import os

from otel_http_test_client import drive

def send(method, url, body):
    ...  # the library under test

drive(os.environ["MOCK_SERVER_URL"], send=send)
```

Each language gets its own implementation under this directory;
[`python/`](python) is the only one so far. `serve_and_drive` is WSGI; an ASGI
framework will need a sibling entry point, sharing `drive` and `REQUESTS`.

The route contract and the request list are in
[`__init__.py`](python/src/otel_http_test_client/__init__.py).
