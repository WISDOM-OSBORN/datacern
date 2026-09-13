"""RAG pipeline: indexing, retrieval and context assembly over Chroma."""

from __future__ import annotations

import hashlib

from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

from datacern.config import settings as config
from datacern.config.providers import active_embedding_provider, get_embeddings

CHROMA_SETTINGS = Settings(anonymized_telemetry=False)


def collection_name_for(filename: str, content_hash: str | None = None) -> str:
    """Deterministic, filesystem-safe collection name.

    Includes a hash of the file *content* (not just the name) so that two
    different files with the same name never share a vector space, while the
    same file content reuses its collection.
    """
    key = f"{filename}:{content_hash or ''}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    stem = "".join(ch if ch.isalnum() else "_" for ch in filename)[:32].strip("_")
    return f"{stem}_{digest}"


def content_hash_for(path: str) -> str:
    """SHA-1 hex digest of a file's bytes."""
    digest = hashlib.sha1()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


class RAGPipeline:
    """Builds/loads a persistent Chroma vector store for a single file."""

    def __init__(self, collection_name: str = "default", embedding_provider: str | None = None):
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider or active_embedding_provider()
        self.embeddings = get_embeddings(self.embedding_provider)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
        )

    # ---------------------------------------------------------- indexing
    def index(self, documents: list) -> int:
        """Split documents, embed and persist them. Returns chunk count.

        Any previous collection with the same name is deleted first so that
        re-running a report never duplicates vectors.
        """
        chunks = self.splitter.split_documents(documents)
        try:
            Chroma(
                embedding_function=self.embeddings,
                persist_directory=str(config.CHROMA_PATH),
                collection_name=self.collection_name,
                client_settings=CHROMA_SETTINGS,
            ).delete_collection()
        except Exception:  # noqa: BLE001  (collection may not exist yet)
            pass
        Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=str(config.CHROMA_PATH),
            collection_name=self.collection_name,
            client_settings=CHROMA_SETTINGS,
        )
        return len(chunks)

    # --------------------------------------------------------- retrieval
    def get_store(self) -> Chroma:
        return Chroma(
            embedding_function=self.embeddings,
            persist_directory=str(config.CHROMA_PATH),
            collection_name=self.collection_name,
            client_settings=CHROMA_SETTINGS,
        )

    def get_retriever(self, k: int = config.TOP_K):
        return self.get_store().as_retriever(search_kwargs={"k": k})

    def retrieve(self, query: str, k: int = config.TOP_K) -> list:
        return self.get_retriever(k=k).invoke(query)

    def retrieve_context(self, query: str, k: int = config.TOP_K) -> str:
        """Return retrieved chunks joined into a single context string."""
        docs = self.retrieve(query, k=k)
        parts = [f"--- chunk {i + 1}/{len(docs)} ---\n{d.page_content}" for i, d in enumerate(docs)]
        return "\n\n".join(parts) if parts else "No relevant context retrieved."
