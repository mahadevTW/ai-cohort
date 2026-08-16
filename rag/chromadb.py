"""Reusable ChromaDB connection and policy-chunk persistence helpers."""

import os
from typing import Any

import chromadb


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PATH = os.path.join(PROJECT_ROOT, "data", "chroma_data")
COLLECTION_NAME = "policies"

_client: Any | None = None
_collection: Any | None = None


def get_collection():
    """Return the policy collection, opening the persistent client only once."""
    global _client, _collection

    if _collection is None:
        print(f"\nOpening ChromaDB at:\n{CHROMA_PATH}")
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    return _collection


def store_chunks(chunks: list[dict], source_file: str):
    """Upsert embedded document chunks into the shared policy collection."""
    if not chunks:
        return get_collection()

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for index, chunk in enumerate(chunks):
        if "Content" not in chunk or "embedding" not in chunk:
            raise ValueError("Each chunk must contain Content and embedding fields.")

        ids.append(str(chunk.get("Id", f"chunk-{index}")))
        documents.append(chunk["Content"])
        embeddings.append(chunk["embedding"])
        metadatas.append({
            "section": chunk.get("section", ""),
            "subsection": chunk.get("Subsection", ""),
            "source": source_file,
        })

    collection = get_collection()
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return collection


def print_records() -> None:
    """Print all stored policy records without including their embedding vectors."""
    collection = get_collection()
    records = collection.get(include=["documents", "metadatas"])

    ids = records.get("ids", [])
    documents = records.get("documents", [])
    metadatas = records.get("metadatas", [])

    print("\n" + "=" * 100)
    print("                    RECORDS IN CHROMADB")
    print("=" * 100)
    print(f"Total records: {len(ids)}")

    if not ids:
        print("No records found.")
        return

    for record_id, document, metadata in zip(ids, documents, metadatas):
        print("\n" + "-" * 100)
        print(f"ID: {record_id}")
        print(f"Metadata: {metadata}")
        print(f"Document:\n{document}")

    print("\n" + "=" * 100)
