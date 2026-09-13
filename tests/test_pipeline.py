"""RAG pipeline tests with stubbed embeddings (no network/API calls)."""

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

import datacern.rag.pipeline as pipeline_mod
from datacern.rag.pipeline import RAGPipeline


class StubEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 10)] * 8 for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0] * 8


@pytest.fixture()
def pipeline(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline_mod.config, "CHROMA_PATH", tmp_path / "chroma")
    monkeypatch.setattr(pipeline_mod, "active_embedding_provider", lambda: "stub")
    monkeypatch.setattr(pipeline_mod, "get_embeddings", lambda provider: StubEmbeddings())
    return RAGPipeline(collection_name="test_collection")


def _docs():
    return [
        Document(page_content="North region revenue was 5000 in January."),
        Document(page_content="South region revenue was 100 in February."),
    ]


def test_index_and_retrieve(pipeline):
    count = pipeline.index(_docs())
    assert count >= 1
    context = pipeline.retrieve_context("revenue by region", k=2)
    assert "revenue" in context.lower()


def test_reindex_does_not_duplicate(pipeline):
    pipeline.index(_docs())
    first = len(pipeline.retrieve("revenue", k=10))
    pipeline.index(_docs())
    second = len(pipeline.retrieve("revenue", k=10))
    assert first == second
