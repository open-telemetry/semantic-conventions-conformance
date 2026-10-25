# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: one langchain retriever query, with no model call.

Adding the documents and running the query both embed against the mock;
nothing else leaves the process. The context-length check is off because it
would make tiktoken fetch its encoding from the internet.
"""

from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

store = InMemoryVectorStore(
    OpenAIEmbeddings(
        model="text-embedding-3-small", check_embedding_ctx_length=False
    )
)
store.add_documents(
    [
        Document(id="seattle", page_content="Seattle is rainy in the winter."),
        Document(id="phoenix", page_content="Phoenix is hot and dry in the summer."),
        Document(id="denver", page_content="Denver gets snow in the mountains."),
    ]
)

store.as_retriever(search_kwargs={"k": 2}).invoke("What is the weather in Seattle?")
