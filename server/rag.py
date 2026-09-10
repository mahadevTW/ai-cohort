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
        from database.chroma import hybrid_search

        # Retrieve a broader candidate set internally, then return a compact,
        # fused result list suitable for the chat prompt.
        results = hybrid_search(query, top_k=top_k, candidate_k=max(12, top_k * 4))
    except Exception:
        logger.exception("Unable to run hybrid policy search for RAG context")
        return ""

    contents = [
        result["text"].strip()
        for result in results
        if result.get("text") and result["text"].strip()
    ]
    if not contents:
        return ""

    return "\n\n---\n\n".join(contents)
