"""Reusable ChromaDB connection and policy-chunk persistence helpers."""

import os
import sys
from typing import Any

# This module intentionally has the same name as the third-party package.
# When `python rag/chroma.py` is used, Python puts `rag/` on sys.path and
# would otherwise import this file again instead of the installed package.
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_original_sys_path = sys.path.copy()

try:
    sys.path = [
        entry
        for entry in sys.path
        if os.path.abspath(entry or os.curdir) != _MODULE_DIR
    ]

    import chromadb as chromadb_client

finally:
    sys.path = _original_sys_path


PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

CHROMA_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "chroma_data",
)

COLLECTION_NAME = "policies"


_client: Any | None = None
_collection: Any | None = None


def get_collection():
    """
    Return the policy collection.

    ChromaDB PersistentClient is initialized only once.
    """

    global _client, _collection

    if _collection is None:

        print(
            f"\nOpening ChromaDB at:\n{CHROMA_PATH}"
        )

        _client = chromadb_client.PersistentClient(
            path=CHROMA_PATH
        )

        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "hnsw:space": "cosine"
            },
        )

    return _collection


def store_chunks(
    chunks: list[dict],
    source_file: str,
):
    """
    Store policy chunks and their embeddings in ChromaDB.

    Expected chunk structure from markdown_chunker.py:

        {
            "Id": "...",
            "Section": "...",
            "Subsection": "...",
            "Content": "...",
            "Metadata": {...},
            "EmbeddingText": "...",
            ...
        }

    Expected embedding structure:

        chunk["embedding"]

    The embedding must have been generated using:

        chunk["EmbeddingText"]

    The actual Content is stored as the ChromaDB document.
    """

    if not chunks:
        print("No chunks to store.")
        return get_collection()

    source_file = str(source_file)

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for index, chunk in enumerate(chunks):

        # ---------------------------------------------------------
        # Validate required fields
        # ---------------------------------------------------------

        if "Content" not in chunk:
            raise ValueError(
                f"Chunk at index {index} is missing 'Content'."
            )

        if "embedding" not in chunk:
            raise ValueError(
                f"Chunk at index {index} is missing 'embedding'. "
                "Generate embeddings using embed_chunks() first."
            )

        if "EmbeddingText" not in chunk:
            raise ValueError(
                f"Chunk at index {index} is missing "
                "'EmbeddingText'."
            )

        # ---------------------------------------------------------
        # ID
        # ---------------------------------------------------------

        chunk_id = chunk.get(
            "Id",
            f"chunk-{index}",
        )

        # Convert ID to string for ChromaDB
        chunk_id = str(chunk_id)

        # ---------------------------------------------------------
        # Document
        # ---------------------------------------------------------
        #
        # IMPORTANT:
        #
        # We store the actual policy content as the Chroma document.
        #
        # The embedding itself was generated from EmbeddingText,
        # which contains the document/section/subsection context.
        #
        # ---------------------------------------------------------

        document = str(
            chunk["Content"]
        )

        # ---------------------------------------------------------
        # Embedding
        # ---------------------------------------------------------

        embedding = chunk["embedding"]

        if not embedding:
            raise ValueError(
                f"Chunk '{chunk_id}' has an empty embedding."
            )

        # ---------------------------------------------------------
        # Metadata
        # ---------------------------------------------------------
        #
        # The new markdown_chunker.py already creates enriched
        # metadata.
        #
        # Example:
        #
        # {
        #     "document_id": "ONB-101",
        #     "document_title": "Employee Onboarding Policy",
        #     "version": "1.4",
        #     "section_number": "4",
        #     "section_title": "Equipment Provisioning",
        #     "subsection_number": "4.2",
        #     "subsection_title": "Remote Hire Shipping",
        #     "chunk_type": "policy",
        #     "keywords": [...],
        #     "systems": [...],
        #     "queues": [...],
        #     "timelines": [...],
        #     "references": [...]
        # }
        #
        # ---------------------------------------------------------

        metadata = chunk.get(
            "Metadata",
            {}
        ).copy()

        # Keep retrieval metadata independent of the local filesystem.
        metadata["source"] = os.path.basename(source_file)

        metadata["source_filename"] = os.path.basename(
            source_file
        )

        # ---------------------------------------------------------
        # ChromaDB metadata must not contain pathlib.Path.
        #
        # Convert every value safely.
        # ---------------------------------------------------------

        metadata = _sanitize_metadata(metadata)

        # ---------------------------------------------------------
        # Add values to batch
        # ---------------------------------------------------------

        ids.append(chunk_id)

        documents.append(document)

        embeddings.append(
            embedding
        )

        metadatas.append(
            metadata
        )

    # -------------------------------------------------------------
    # Upsert into ChromaDB
    # -------------------------------------------------------------

    collection = get_collection()

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(
        f"\nSuccessfully stored {len(ids)} chunks "
        f"from {source_file}"
    )

    return collection


def _sanitize_metadata(
    metadata: dict,
) -> dict:
    """
    Convert metadata into values supported by ChromaDB.

    Supported values:
        str
        int
        float
        bool
        list
        None

    pathlib.Path and other unsupported objects are converted
    to strings.
    """

    sanitized = {}

    for key, value in metadata.items():

        key = str(key)

        if value is None:
            sanitized[key] = None

        elif isinstance(
            value,
            (str, int, float, bool),
        ):
            sanitized[key] = value

        elif isinstance(value, list):
            cleaned_values = [
                str(item)
                for item in value
            ]

            if cleaned_values:
                sanitized[key] = cleaned_values

        else:
            sanitized[key] = str(value)

    return sanitized


def print_records() -> None:
    """
    Print all stored policy records without embedding vectors.
    """

    collection = get_collection()

    records = collection.get(
        include=[
            "documents",
            "metadatas",
        ]
    )

    ids = records.get(
        "ids",
        []
    )

    documents = records.get(
        "documents",
        []
    )

    metadatas = records.get(
        "metadatas",
        []
    )

    print(
        "\n" + "=" * 100
    )

    print(
        "                    RECORDS IN CHROMADB"
    )

    print(
        "=" * 100
    )

    print(
        f"Total records: {len(ids)}"
    )

    if not ids:
        print(
            "No records found."
        )
        return

    for index, (
        record_id,
        document,
        metadata,
    ) in enumerate(
        zip(
            ids,
            documents,
            metadatas,
        ),
        start=1,
    ):

        print(
            "\n" + "-" * 100
        )

        print(
            f"Record #{index}"
        )

        print(
            f"ID: {record_id}"
        )

        print(
            f"Metadata: {metadata}"
        )

        print(
            f"Document:\n{document}"
        )

    print(
        "\n" + "=" * 100
    )


def print_vectors() -> None:
    """
    Print the embedding vector for every record stored in ChromaDB.
    """

    collection = get_collection()

    records = collection.get(
        include=[
            "embeddings"
        ]
    )

    ids = records.get(
        "ids",
        []
    )

    embeddings = records.get(
        "embeddings",
        []
    )

    print(
        "\n" + "=" * 100
    )

    print(
        "                    VECTOR REPRESENTATIONS"
    )

    print(
        "=" * 100
    )

    print(
        f"Total records: {len(ids)}"
    )

    if not ids:
        print(
            "No records found."
        )
        return

    for index, record_id in enumerate(
        ids
    ):

        vector = embeddings[index]

        print(
            "\n" + "-" * 100
        )

        print(
            f"Record #{index + 1}"
        )

        print(
            f"ID: {record_id}"
        )

        print(
            f"Vector dimensions: {len(vector)}"
        )

        print(
            "\nVector:"
        )

        print(
            vector
        )

    print(
        "\n" + "=" * 100
    )