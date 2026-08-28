"""
RAG query functionality.

Retrieval pipeline:

User Query
    ↓
Query Expansion
    ↓
For EACH expanded query:
    ├── Semantic Search
    │       ChromaDB + all-MiniLM-L6-v2
    │       Top 15
    │
    └── Keyword Search
            BM25
            Top 15
    ↓
Merge / Deduplicate
    ↓
Reciprocal Rank Fusion
    ↓
Final Top K
    ↓
RAG Context
    ↓
LLM

Important:
- No CrossEncoder
- No optional reranker
- Embeddings are NOT sent to the LLM
- Only retrieved document text + metadata are sent to the LLM
- Query expansion happens for EVERY user-provided query
"""

from __future__ import annotations

import os
import re
from typing import Any

from rank_bm25 import BM25Okapi

from rag.embedder import embed_chunks
from rag.chromadb import get_collection


# ============================================================
# CONFIGURATION
# ============================================================

# Number of candidates retrieved from semantic search
# for EACH expanded query.
SEMANTIC_CANDIDATES = int(
    os.getenv(
        "RAG_SEMANTIC_CANDIDATES",
        "15",
    )
)


# Number of candidates retrieved from BM25
# for EACH expanded query.
BM25_CANDIDATES = int(
    os.getenv(
        "RAG_BM25_CANDIDATES",
        "15",
    )
)


# Number of chunks finally returned to the LLM.
FINAL_RESULTS = int(
    os.getenv(
        "RAG_FINAL_RESULTS",
        "5",
    )
)


# ============================================================
# QUERY EXPANSION
# ============================================================

# Domain-specific aliases.
#
# These help bridge differences between the language used by
# users and terminology used in policy documents.
#
# The ORIGINAL user query is always retained.
#
# Example:
#
# User:
#     "My laptop hasn't arrived"
#
# Expanded queries:
#
#     "My laptop hasn't arrived laptop equipment device"
#
#     "My laptop hasn't arrived missing not received shipping equipment"
#
# These are generated from the actual user query.
#
# There is NO hardcoded user question here.

DOMAIN_ALIASES = {
    "laptop": "laptop equipment device",
    "computer": "computer laptop equipment device",
    "pc": "computer laptop equipment device",

    "joining": "joining start date onboarding",
    "join": "joining start date onboarding",

    "new joiner": "new hire onboarding employee",
    "new employee": "new hire onboarding employee",

    "account": "account access identity",
    "login": "login access account",
    "log in": "login access account",

    "access": "access provisioning account",
    "permissions": "permissions access provisioning",

    "okta": "Okta SSO account access",

    "probation": "probation evaluation review",

    "training": "training learning e-learning",
    "course": "training learning e-learning",

    "manager": "manager hiring manager",
    "boss": "manager hiring manager",

    "ticket": "ticket ServiceDesk request",
    "issue": "issue blocker ticket escalation",
    "problem": "problem blocker issue escalation",

    "not working": "failure issue blocker troubleshooting",

    "missing": "missing unavailable not received",

    "hasn't arrived": (
        "missing not received shipping equipment"
    ),

    "has not arrived": (
        "missing not received shipping equipment"
    ),

    "deadline": (
        "deadline timeline SLA due date"
    ),

    "how long": (
        "duration timeline SLA days"
    ),

    "when": (
        "timeline date deadline"
    ),
}


def preprocess_query(query: str) -> list[str]:
    """
    Normalize and expand the user's query.

    The original user query is ALWAYS retained.

    Every matching domain alias produces an additional
    retrieval query.

    Example:

        User query:
            My laptop hasn't arrived. What should I do?

        Expanded queries:

            1. My laptop hasn't arrived. What should I do?

            2. My laptop hasn't arrived. What should I do?
               laptop equipment device

            3. My laptop hasn't arrived. What should I do?
               missing not received shipping equipment

    This function does NOT use an LLM.

    The original query is retained because exact terms such as:

        Okta
        Workday
        ServiceDesk
        NEWHIRE-PROV
        IT-ACCESS
        HR-EXCEPTIONS

    are valuable for BM25 retrieval.
    """

    if not query or not query.strip():
        raise ValueError(
            "Query cannot be empty."
        )

    # --------------------------------------------------------
    # Normalize whitespace.
    # --------------------------------------------------------

    query = query.strip()

    query = re.sub(
        r"\s+",
        " ",
        query,
    )

    normalized_query = query.lower()

    # --------------------------------------------------------
    # Always retain the original user query.
    # --------------------------------------------------------

    expanded_queries: list[str] = [
        query
    ]

    # --------------------------------------------------------
    # Generate expanded queries.
    #
    # IMPORTANT:
    # These expansions are generated from the actual query
    # supplied by the user.
    # --------------------------------------------------------

    for phrase, expansion in DOMAIN_ALIASES.items():

        if phrase in normalized_query:

            expanded_query = (
                f"{query} {expansion}"
            )

            # Avoid duplicate expanded queries.
            if expanded_query not in expanded_queries:

                expanded_queries.append(
                    expanded_query
                )

    # --------------------------------------------------------
    # Print expanded queries.
    # --------------------------------------------------------

    print("\n" + "=" * 100)
    print("QUERY EXPANSION")
    print("=" * 100)

    print(
        f"Original Query: {query}"
    )

    print(
        f"Expanded Query Count: "
        f"{len(expanded_queries)}"
    )

    print("\nExpanded Queries:")

    for index, expanded_query in enumerate(
        expanded_queries,
        start=1,
    ):

        print(
            f"{index}. {expanded_query}"
        )

    print("=" * 100)

    return expanded_queries


# ============================================================
# TOKENIZATION
# ============================================================

def tokenize(text: str) -> list[str]:
    """
    Tokenize text for BM25.

    The tokenizer intentionally preserves hyphenated
    identifiers such as:

        NEWHIRE-PROV
        IT-ACCESS
        HR-EXCEPTIONS

    It also preserves numbers such as:

        2
        5
        10
        14
        30
        90

    This is useful for policy questions involving SLAs,
    timelines and ticket queues.
    """

    if not text:
        return []

    text = text.lower()

    return re.findall(
        r"[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*",
        text,
    )


# ============================================================
# SEMANTIC SEARCH
# ============================================================

def semantic_search(
    query: str,
    n_results: int = SEMANTIC_CANDIDATES,
) -> dict[str, Any]:
    """
    Search ChromaDB using semantic similarity.

    The same embedding implementation used during ingestion
    is used for the query through embed_chunks().
    """

    if not query or not query.strip():
        raise ValueError(
            "Query cannot be empty."
        )

    # The existing embed_chunks() function expects chunks
    # containing a "Content" field.
    query_chunk = {
        "Content": query
    }

    # Generate query embedding using the existing embedding
    # implementation.
    embedded_query = embed_chunks(
        [query_chunk]
    )

    if not embedded_query:
        raise ValueError(
            "Failed to generate query embedding."
        )

    # Support the embedding format returned by the existing
    # embedder implementation.
    #
    # If embed_chunks() returns:
    #
    #     [[0.1, 0.2, ...]]
    #
    # use embedded_query[0].
    #
    # If it returns:
    #
    #     [{"embedding": [0.1, 0.2, ...]}]
    #
    # use the "embedding" field.

    first_embedding = embedded_query[0]

    if isinstance(first_embedding, dict):

        query_embedding = first_embedding.get(
            "embedding"
        )

    else:

        query_embedding = first_embedding

    if query_embedding is None:
        raise ValueError(
            "Query embedding is missing."
        )

    # Get the shared ChromaDB collection.
    collection = get_collection()

    # Perform semantic similarity search.
    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=n_results,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    return results


# ============================================================
# BM25 SEARCH
# ============================================================

def bm25_search(
    query: str,
    n_results: int = BM25_CANDIDATES,
) -> dict[str, Any]:
    """
    Perform BM25 keyword search over documents stored
    in ChromaDB.

    This is useful for exact policy terminology such as:

        NEWHIRE-PROV
        IT-ACCESS
        HR-EXCEPTIONS
        Okta
        Workday
        2 business days
        90 calendar days
        P1
        P2

    Note:

        This implementation loads all Chroma documents for
        every query. That is acceptable for a small/medium
        policy collection.

        For a very large collection, use a persistent lexical
        search index such as Elasticsearch/OpenSearch/SQLite
        FTS instead.
    """

    if not query or not query.strip():
        raise ValueError(
            "Query cannot be empty."
        )

    collection = get_collection()

    # Retrieve all policy documents from ChromaDB.
    all_records = collection.get(
        include=[
            "documents",
            "metadatas",
        ],
    )

    documents = (
        all_records.get("documents")
        or []
    )

    metadatas = (
        all_records.get("metadatas")
        or []
    )

    ids = (
        all_records.get("ids")
        or []
    )

    if not documents:

        return {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    # Tokenize every policy document.
    tokenized_documents = [
        tokenize(document)
        for document in documents
    ]

    # Create BM25 index.
    bm25 = BM25Okapi(
        tokenized_documents
    )

    # Tokenize user query.
    query_tokens = tokenize(
        query
    )

    if not query_tokens:

        return {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }

    # Calculate BM25 relevance scores.
    scores = bm25.get_scores(
        query_tokens
    )

    # Sort documents by BM25 score.
    ranked_indexes = sorted(
        range(len(scores)),
        key=lambda index: scores[index],
        reverse=True,
    )

    # Keep only top candidates.
    ranked_indexes = ranked_indexes[
        :n_results
    ]

    result_ids = [
        ids[index]
        for index in ranked_indexes
    ]

    result_documents = [
        documents[index]
        for index in ranked_indexes
    ]

    result_metadatas = [
        metadatas[index]
        for index in ranked_indexes
    ]

    result_scores = [
        float(scores[index])
        for index in ranked_indexes
    ]

    return {
        "ids": [
            result_ids
        ],
        "documents": [
            result_documents
        ],
        "metadatas": [
            result_metadatas
        ],
        "distances": [
            result_scores
        ],
    }


# ============================================================
# RESULT CONVERSION
# ============================================================

def result_to_records(
    results: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert Chroma-style search results into a simple
    list of dictionaries.

    This makes it easier to perform fusion.
    """

    ids = results.get(
        "ids",
        [[]],
    )[0]

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    distances = results.get(
        "distances",
        [[]],
    )[0]

    records: list[dict[str, Any]] = []

    for index, record_id in enumerate(ids):

        record = {
            "id": record_id,

            "document": (
                documents[index]
                if index < len(documents)
                else ""
            ),

            "metadata": (
                metadatas[index]
                if index < len(metadatas)
                else {}
            ),

            "score": (
                distances[index]
                if index < len(distances)
                else None
            ),
        }

        records.append(
            record
        )

    return records


# ============================================================
# MERGE MULTIPLE SEARCH RESULTS
# ============================================================

def merge_search_results(
    results_list: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Merge search results from multiple expanded queries.

    A document can be retrieved by more than one expanded query.

    Example:

        Query 1 -> Chunk A, Chunk B, Chunk C
        Query 2 -> Chunk B, Chunk D, Chunk A
        Query 3 -> Chunk A, Chunk E, Chunk B

    Final merged result:

        Chunk A
        Chunk B
        Chunk C
        Chunk D
        Chunk E

    Duplicate chunks are removed.

    The best (lowest) distance/score encountered for a chunk
    is retained.
    """

    combined: dict[
        str,
        dict[str, Any]
    ] = {}

    for results in results_list:

        records = result_to_records(
            results
        )

        for rank, record in enumerate(
            records,
            start=1,
        ):

            record_id = record["id"]

            if record_id not in combined:

                combined[record_id] = {
                    **record,
                    "best_rank": rank,
                    "match_count": 1,
                }

            else:

                combined[
                    record_id
                ]["match_count"] += 1

                # Keep the best rank.
                if rank < combined[
                    record_id
                ]["best_rank"]:

                    combined[
                        record_id
                    ]["best_rank"] = rank

                # Keep the best distance/score.
                existing_score = combined[
                    record_id
                ].get("score")

                current_score = record.get(
                    "score"
                )

                if (
                    current_score is not None
                    and (
                        existing_score is None
                        or current_score < existing_score
                    )
                ):

                    combined[
                        record_id
                    ]["score"] = current_score

    # --------------------------------------------------------
    # Rank merged results.
    #
    # Documents appearing in multiple expanded-query searches
    # are preferred.
    #
    # Then use their best rank.
    # --------------------------------------------------------

    merged_records = sorted(
        combined.values(),
        key=lambda record: (
            -record["match_count"],
            record["best_rank"],
        ),
    )

    return {
        "ids": [
            [
                record["id"]
                for record in merged_records
            ]
        ],

        "documents": [
            [
                record["document"]
                for record in merged_records
            ]
        ],

        "metadatas": [
            [
                record["metadata"]
                for record in merged_records
            ]
        ],

        "distances": [
            [
                record["score"]
                for record in merged_records
            ]
        ],
    }


# ============================================================
# RECIPROCAL RANK FUSION
# ============================================================

def reciprocal_rank_fusion(
    semantic_results: dict[str, Any],
    keyword_results: dict[str, Any],
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Combine semantic-search and BM25 rankings using
    Reciprocal Rank Fusion (RRF).

    RRF:

        score = 1 / (k + rank)

    A document that appears in both semantic and keyword
    search receives contributions from both rankings.

    This is preferable to directly adding Chroma distances
    and BM25 scores because those values are on different
    scales.
    """

    semantic_records = result_to_records(
        semantic_results
    )

    keyword_records = result_to_records(
        keyword_results
    )

    combined: dict[
        str,
        dict[str, Any]
    ] = {}

    # --------------------------------------------------------
    # Semantic search ranking
    # --------------------------------------------------------

    for rank, record in enumerate(
        semantic_records,
        start=1,
    ):

        record_id = record["id"]

        if record_id not in combined:

            combined[record_id] = {
                **record,
                "semantic_rank": rank,
                "keyword_rank": None,
                "rrf_score": 0.0,
            }

        else:

            # Keep the best semantic rank.
            existing_rank = combined[
                record_id
            ].get("semantic_rank")

            if (
                existing_rank is None
                or rank < existing_rank
            ):

                combined[
                    record_id
                ]["semantic_rank"] = rank

        combined[
            record_id
        ]["rrf_score"] += (
            1.0 / (k + rank)
        )

    # --------------------------------------------------------
    # BM25 keyword ranking
    # --------------------------------------------------------

    for rank, record in enumerate(
        keyword_records,
        start=1,
    ):

        record_id = record["id"]

        if record_id not in combined:

            combined[record_id] = {
                **record,
                "semantic_rank": None,
                "keyword_rank": rank,
                "rrf_score": 0.0,
            }

        else:

            existing_rank = combined[
                record_id
            ].get("keyword_rank")

            if (
                existing_rank is None
                or rank < existing_rank
            ):

                combined[
                    record_id
                ]["keyword_rank"] = rank

        combined[
            record_id
        ]["rrf_score"] += (
            1.0 / (k + rank)
        )

    # --------------------------------------------------------
    # Sort highest RRF score first.
    # --------------------------------------------------------

    ranked_records = sorted(
        combined.values(),
        key=lambda record: record[
            "rrf_score"
        ],
        reverse=True,
    )

    return ranked_records


# ============================================================
# RECORDS → CHROMA STYLE RESULTS
# ============================================================

def records_to_results(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Convert internal records back to the Chroma-style result
    structure expected by build_rag_context().
    """

    return {
        "ids": [
            [
                record["id"]
                for record in records
            ]
        ],

        "documents": [
            [
                record.get(
                    "document",
                    "",
                )
                for record in records
            ]
        ],

        "metadatas": [
            [
                record.get(
                    "metadata",
                    {},
                )
                for record in records
            ]
        ],

        "distances": [
            [
                record.get(
                    "rrf_score"
                )
                for record in records
            ]
        ],
    }


# ============================================================
# MAIN HYBRID SEARCH WITH QUERY EXPANSION
# ============================================================

def search_chromadb(
    query: str,
    n_results: int = FINAL_RESULTS,
) -> dict[str, Any]:
    """
    Main hybrid retrieval function.

    IMPORTANT:

        `query` is the actual user-provided query coming
        from server.py.

    Every user query goes through query expansion.

    Pipeline:

        User Query
             ↓
        Query Expansion
             ↓
        Expanded Query 1
             ├── Semantic Search
             └── BM25 Search
                    ↓
        Expanded Query 2
             ├── Semantic Search
             └── BM25 Search
                    ↓
                  ...
                    ↓
        Merge Semantic Results
        Merge BM25 Results
                    ↓
        Reciprocal Rank Fusion
                    ↓
        Final Top K
    """

    if not query or not query.strip():

        raise ValueError(
            "Query cannot be empty."
        )

    # ========================================================
    # 1. QUERY EXPANSION
    # ========================================================

    expanded_queries = preprocess_query(
        query
    )

    print("\n" + "=" * 100)
    print("HYBRID RAG SEARCH WITH QUERY EXPANSION")
    print("=" * 100)

    print(
        f"Original query: {query}"
    )

    print(
        f"Expanded query count: "
        f"{len(expanded_queries)}"
    )

    # ========================================================
    # 2. SEARCH EVERY EXPANDED QUERY
    # ========================================================

    all_semantic_results: list[
        dict[str, Any]
    ] = []

    all_keyword_results: list[
        dict[str, Any]
    ] = []

    for index, expanded_query in enumerate(
        expanded_queries,
        start=1,
    ):

        print("\n")
        print("-" * 100)

        print(
            f"PROCESSING EXPANDED QUERY "
            f"{index}/{len(expanded_queries)}"
        )

        print(
            f"Query: {expanded_query}"
        )

        print("-" * 100)

        # ----------------------------------------------------
        # Semantic search
        # ----------------------------------------------------

        semantic_results = semantic_search(
            expanded_query,
            n_results=SEMANTIC_CANDIDATES,
        )

        semantic_count = len(
            semantic_results.get(
                "ids",
                [[]],
            )[0]
        )

        print(
            f"Semantic candidates: "
            f"{semantic_count}"
        )

        all_semantic_results.append(
            semantic_results
        )

        # ----------------------------------------------------
        # BM25 search
        # ----------------------------------------------------

        keyword_results = bm25_search(
            expanded_query,
            n_results=BM25_CANDIDATES,
        )

        keyword_count = len(
            keyword_results.get(
                "ids",
                [[]],
            )[0]
        )

        print(
            f"BM25 candidates: "
            f"{keyword_count}"
        )

        all_keyword_results.append(
            keyword_results
        )

    # ========================================================
    # 3. MERGE SEMANTIC RESULTS
    # ========================================================

    merged_semantic_results = merge_search_results(
        all_semantic_results
    )

    # ========================================================
    # 4. MERGE BM25 RESULTS
    # ========================================================

    merged_keyword_results = merge_search_results(
        all_keyword_results
    )

    print("\n")
    print("=" * 100)
    print("MERGED SEARCH RESULTS")
    print("=" * 100)

    merged_semantic_count = len(
        merged_semantic_results.get(
            "ids",
            [[]],
        )[0]
    )

    merged_keyword_count = len(
        merged_keyword_results.get(
            "ids",
            [[]],
        )[0]
    )

    print(
        f"Merged semantic candidates: "
        f"{merged_semantic_count}"
    )

    print(
        f"Merged BM25 candidates: "
        f"{merged_keyword_count}"
    )

    # ========================================================
    # 5. RECIPROCAL RANK FUSION
    # ========================================================

    fused_results = reciprocal_rank_fusion(
        merged_semantic_results,
        merged_keyword_results,
    )

    print(
        f"Fused candidates: "
        f"{len(fused_results)}"
    )

    # ========================================================
    # 6. SELECT FINAL TOP K
    # ========================================================

    final_records = fused_results[
        :n_results
    ]

    # ========================================================
    # 7. DEBUG INFORMATION
    # ========================================================

    print("\n")
    print("=" * 100)
    print("FINAL RETRIEVED CHUNKS")
    print("=" * 100)

    for index, record in enumerate(
        final_records,
        start=1,
    ):

        metadata = record.get(
            "metadata",
            {},
        )

        print(
            f"\n{index}. "
            f"ID={record['id']}"
        )

        print(
            f"   RRF Score="
            f"{record.get('rrf_score')}"
        )

        print(
            f"   Semantic Rank="
            f"{record.get('semantic_rank')}"
        )

        print(
            f"   BM25 Rank="
            f"{record.get('keyword_rank')}"
        )

        print(
            f"   Metadata={metadata}"
        )

        print(
            "\n   Content:"
        )

        print(
            record.get(
                "document",
                "",
            )
        )

    print(
        "\n" + "=" * 100
    )

    return records_to_results(
        final_records
    )


# ============================================================
# BUILD RAG CONTEXT
# ============================================================

def build_rag_context(
    results: dict[str, Any],
) -> str:
    """
    Convert retrieved policy chunks into text context
    that can be passed to the LLM.

    IMPORTANT:

    The vector embeddings themselves are NOT sent to the LLM.

    Only:

        - policy content
        - document metadata
        - retrieval score

    are included.
    """

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    distances = results.get(
        "distances",
        [[]],
    )[0]

    if not documents:
        return ""

    context_parts: list[str] = []

    for index, document in enumerate(
        documents
    ):

        metadata = (
            metadatas[index]
            if index < len(metadatas)
            else {}
        )

        score = (
            distances[index]
            if index < len(distances)
            else None
        )

        # ----------------------------------------------------
        # Source
        # ----------------------------------------------------

        source = metadata.get(
            "source_filename",
            metadata.get(
                "source",
                metadata.get(
                    "file_path",
                    "Unknown",
                ),
            ),
        )

        # Older records may still contain an absolute source path.
        if source not in (
            None,
            "Unknown",
        ):

            source = os.path.basename(
                str(source)
            )

        # ----------------------------------------------------
        # Document title
        # ----------------------------------------------------

        title = metadata.get(
            "title",
            metadata.get(
                "document_title",
                "",
            ),
        )

        # ----------------------------------------------------
        # Document ID
        # ----------------------------------------------------

        document_id = metadata.get(
            "document_id",
            "",
        )

        # ----------------------------------------------------
        # Version
        # ----------------------------------------------------

        version = metadata.get(
            "version",
            "",
        )

        # ----------------------------------------------------
        # Section
        # ----------------------------------------------------

        section = metadata.get(
            "section",
            metadata.get(
                "section_title",
                "",
            ),
        )

        section_number = metadata.get(
            "section_number",
            "",
        )

        # ----------------------------------------------------
        # Subsection
        # ----------------------------------------------------

        subsection = metadata.get(
            "Subsection",
            metadata.get(
                "subsection_title",
                "",
            ),
        )

        subsection_number = metadata.get(
            "subsection_number",
            "",
        )

        # ----------------------------------------------------
        # Chunk type
        # ----------------------------------------------------

        chunk_type = metadata.get(
            "chunk_type",
            "",
        )

        context_parts.append(
            f"""
--- POLICY CHUNK {index + 1} ---

Document ID: {document_id}
Source: {source}
Title: {title}
Version: {version}

Section: {section_number} {section}
Subsection: {subsection_number} {subsection}
Chunk Type: {chunk_type}

Retrieval Score: {score}

Content:
{document}
"""
        )

    return "\n".join(
        context_parts
    )


# ============================================================
# DEBUG SEARCH RESULTS
# ============================================================

def print_search_results(
    results: dict[str, Any],
) -> None:
    """
    Print final retrieved chunks from the hybrid search.
    """

    ids = results.get(
        "ids",
        [[]],
    )[0]

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    distances = results.get(
        "distances",
        [[]],
    )[0]

    print(
        "\n" + "=" * 100
    )

    print(
        "CHROMADB HYBRID SEARCH RESULTS"
    )

    print(
        "=" * 100
    )

    print(
        f"Results found: {len(ids)}"
    )

    for index, record_id in enumerate(
        ids
    ):

        print(
            "\n" + "-" * 100
        )

        print(
            f"Result #{index + 1}"
        )

        print(
            f"ID: {record_id}"
        )

        if index < len(distances):

            print(
                f"RRF Score: "
                f"{distances[index]}"
            )

        if index < len(metadatas):

            print(
                f"Metadata: "
                f"{metadatas[index]}"
            )

        print(
            "\nContent:"
        )

        if index < len(documents):

            print(
                documents[index]
            )

    print(
        "\n" + "=" * 100
    )