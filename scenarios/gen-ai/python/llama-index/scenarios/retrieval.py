# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: one LlamaIndex retriever query, with no model call.

The documents are nodes already, so indexing needs no splitter and no
tokenizer download. Building the index and running the query both embed
against the mock; nothing else leaves the process.
"""

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.embeddings.openai import OpenAIEmbedding

nodes = [
    TextNode(id_="seattle", text="Seattle is rainy in the winter."),
    TextNode(id_="phoenix", text="Phoenix is hot and dry in the summer."),
    TextNode(id_="denver", text="Denver gets snow in the mountains."),
]

index = VectorStoreIndex(
    nodes=nodes, embed_model=OpenAIEmbedding(model="text-embedding-3-small")
)

index.as_retriever(similarity_top_k=2).retrieve("What is the weather in Seattle?")
