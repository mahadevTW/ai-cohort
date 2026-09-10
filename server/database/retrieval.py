"""Dependency-free lexical ranking utilities used by policy retrieval."""

from collections import Counter
import math
import re


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _tokens(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


def bm25_rank(query: str, documents: dict[str, str], limit: int) -> list[str]:
    """Rank document IDs by BM25 without introducing another service or dependency."""
    query_tokens = _tokens(query)
    if not query_tokens or not documents:
        return []

    tokenised_documents = {document_id: _tokens(text) for document_id, text in documents.items()}
    document_count = len(tokenised_documents)
    average_length = sum(len(tokens) for tokens in tokenised_documents.values()) / document_count
    document_frequency = Counter(
        token for tokens in tokenised_documents.values() for token in set(tokens)
    )
    scores: dict[str, float] = {}
    for document_id, tokens in tokenised_documents.items():
        frequency = Counter(tokens)
        score = 0.0
        for token in query_tokens:
            if token not in frequency:
                continue
            idf = math.log(1 + (document_count - document_frequency[token] + 0.5) /
                           (document_frequency[token] + 0.5))
            denominator = frequency[token] + 1.5 * (1 - 0.75 + 0.75 * len(tokens) / average_length)
            score += idf * (frequency[token] * 2.5) / denominator
        if score:
            scores[document_id] = score
    return [document_id for document_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]]


def reciprocal_rank_fusion(*rankings: list[str], limit: int, rank_constant: int = 60) -> list[str]:
    """Merge rankings while rewarding chunks selected by either retrieval method."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, document_id in enumerate(ranking, start=1):
            scores[document_id] = scores.get(document_id, 0.0) + 1 / (rank_constant + rank)
    return [document_id for document_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]]
