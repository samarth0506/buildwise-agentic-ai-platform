"""
BuildWise RAG retriever — FAISS vector store with local HuggingFace embeddings.

Build once, save under ``vectorstore/faiss_index/``, reload on subsequent runs.
No paid or cloud embedding APIs.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from rag.data_loader import load_all_documents

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FAISS_INDEX_DIR = PROJECT_ROOT / "vectorstore" / "faiss_index"

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Cached embedding model and vectorstore (avoid reloading on every query)
_embedding_model: Optional[HuggingFaceEmbeddings] = None
_vectorstore: Optional[FAISS] = None


class NoDocumentsError(Exception):
    """Raised when no source documents are available to build or query the index."""


def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    Return a shared HuggingFace embedding model (CPU, local only).

    Uses ``sentence-transformers/all-MiniLM-L6-v2`` — no API keys required.
    """
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("Loaded embedding model: %s", EMBEDDING_MODEL_NAME)
    return _embedding_model


def _index_exists() -> bool:
    """True if a previously saved FAISS index is on disk."""
    faiss_file = FAISS_INDEX_DIR / "index.faiss"
    pkl_file = FAISS_INDEX_DIR / "index.pkl"
    return faiss_file.is_file() and pkl_file.is_file()


def _save_vectorstore(store: FAISS) -> None:
    """Persist FAISS index to ``vectorstore/faiss_index/``."""
    FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(FAISS_INDEX_DIR))
    logger.info("Saved FAISS index to %s", FAISS_INDEX_DIR)


def _load_vectorstore(embeddings: HuggingFaceEmbeddings) -> FAISS:
    """Load a saved FAISS index from disk."""
    return FAISS.load_local(
        str(FAISS_INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def build_vectorstore(force_rebuild: bool = False) -> FAISS:
    """
    Build or load the FAISS vector store.

    Args:
        force_rebuild: If True, delete any saved index and rebuild from data.

    Returns:
        FAISS vector store ready for similarity search.

    Raises:
        NoDocumentsError: If no documents were loaded from ``data/``.
    """
    global _vectorstore

    embeddings = get_embedding_model()

    if force_rebuild and FAISS_INDEX_DIR.exists():
        shutil.rmtree(FAISS_INDEX_DIR)
        logger.info("Removed existing FAISS index (force_rebuild=True)")

    if not force_rebuild and _vectorstore is not None:
        return _vectorstore

    if not force_rebuild and _index_exists():
        logger.info("Loading existing FAISS index from %s", FAISS_INDEX_DIR)
        _vectorstore = _load_vectorstore(embeddings)
        return _vectorstore

    documents = load_all_documents()
    if not documents:
        raise NoDocumentsError(
            "No documents found to build the vector store. "
            f"Add CSV/TXT files under: {PROJECT_ROOT / 'data'}"
        )

    logger.info("Building FAISS index from %d document(s)...", len(documents))
    _vectorstore = FAISS.from_documents(documents, embeddings)
    _save_vectorstore(_vectorstore)
    return _vectorstore


def retrieve_context(query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Retrieve the top-k most relevant document chunks for a query.

    Args:
        query: Natural-language question (e.g. ``Why is Tower B delayed?``).
        top_k: Number of chunks to return.

    Returns:
        List of dicts with keys: ``content``, ``metadata``, ``similarity_score``.

    Raises:
        NoDocumentsError: If the vector store cannot be built (no data).
    """
    store = build_vectorstore()
    # Relevance scores are normalized to [0, 1] where higher is more similar
    results = store.similarity_search_with_relevance_scores(query, k=top_k)

    context_chunks: List[Dict[str, Any]] = []
    for document, score in results:
        context_chunks.append(
            {
                "content": document.page_content,
                "metadata": dict(document.metadata),
                "similarity_score": float(score),
            }
        )
    return context_chunks


def retrieve_context_text(query: str, top_k: int = 4) -> str:
    """
    Retrieve context and return a single formatted string for LLM prompts.

    Args:
        query: Natural-language question.
        top_k: Number of chunks to include.

    Returns:
        Clean multi-section text with source, category, and scores.
    """
    chunks = retrieve_context(query, top_k=top_k)
    if not chunks:
        return ""

    sections: List[str] = []
    for index, chunk in enumerate(chunks, start=1):
        meta = chunk["metadata"]
        source = meta.get("source", "unknown")
        category = meta.get("category", "unknown")
        score = chunk["similarity_score"]
        row_or_chunk = meta.get("row_number") or meta.get("chunk_number", "n/a")

        header = (
            f"[{index}] source={source} | category={category} | "
            f"ref={row_or_chunk} | relevance={score:.3f}"
        )
        sections.append(f"{header}\n{chunk['content']}")

    return "\n\n---\n\n".join(sections)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    demo_query = "Why is Tower B delayed?"
    print(f"Demo query: {demo_query}\n")

    try:
        # First run builds index; later runs reload from vectorstore/faiss_index/
        build_vectorstore(force_rebuild=False)

        print("=== retrieve_context ===")
        results = retrieve_context(demo_query, top_k=4)
        for item in results:
            print(f"\nScore: {item['similarity_score']:.3f}")
            print(f"Metadata: {item['metadata']}")
            print(f"Content: {item['content'][:300]}...")

        print("\n=== retrieve_context_text ===")
        print(retrieve_context_text(demo_query, top_k=4))

    except NoDocumentsError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc
