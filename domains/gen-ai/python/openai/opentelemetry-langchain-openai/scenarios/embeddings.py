# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: OpenAI embeddings, through langchain.

``check_embedding_ctx_length`` is off because it is on by default: langchain
would tokenize locally with tiktoken, downloading the encoding over the
network on first use and then sending token ids instead of the text. Off, the
request carries the same two strings as openai/scenarios/embeddings.py.

langchain does not expose ``encoding_format``, so unlike the openai SDK
scenario this request does not name one.
"""

from langchain_openai import OpenAIEmbeddings

OpenAIEmbeddings(
    model="text-embedding-3-small",
    dimensions=256,
    check_embedding_ctx_length=False,
).embed_documents(["Say this is a test", "And this is another one"])
