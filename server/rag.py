"""Retrieval-augmented generation helpers for the chat request flow."""

import logging

logger = logging.getLogger(__name__)


def get_rag_context(query: str, top_k: int = 3) -> str:
    """Return relevant document chunks for *query*, or an empty string on failure.

    Retrieval is deliberately best-effort: a Chroma or embedding problem must not
    prevent the normal chat and conversation-history flow from working.
    """
    if not query or not query.strip():
        return ""

    try:
        # Import lazily so an unavailable embedding model cannot stop the chat
        # application from starting.
        from database.chroma import embed, search_vectors

        query_vector = embed(query)
    except Exception:
        logger.exception("Unable to create an embedding for the RAG query")
        return ""

    try:
        results = search_vectors(query_vector=query_vector, top_k=top_k)
    except Exception:
        logger.exception("Unable to search ChromaDB for RAG context")
        return ""

    contents = [
        result["text"].strip()
        for result in results
        if result.get("text") and result["text"].strip()
    ]
    if not contents:
        return ""

    return "\n\n---\n\n".join(contents)
