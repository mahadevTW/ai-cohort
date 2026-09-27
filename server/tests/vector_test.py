import uuid

import pytest

from database.chroma import VectorStore


TEST_DB = "./test_chroma_db"


@pytest.fixture
def store():

    collection_name = f"test_{uuid.uuid4().hex}"

    return VectorStore(
        collection_name=collection_name,
        persist_directory=TEST_DB
    )


def test_save_vector(store):

    vector = [1.0, 0.0, 0.0, 0.0]

    document_id = store.save_vector(
        vector=vector,
        text="Python is a programming language",
        metadata={
            "source": "python.txt",
            "type": "document"
        },
        document_id="doc_1"
    )

    assert document_id == "doc_1"

    result = store.collection.get()

    assert len(result["ids"]) == 1
    assert result["ids"][0] == "doc_1"

    assert result["documents"][0] == (
        "Python is a programming language"
    )


def test_search_vector(store):

    store.save_vector(
        vector=[1.0, 0.0, 0.0, 0.0],
        text="Python is a programming language",
        metadata={
            "language": "python"
        },
        document_id="python"
    )

    store.save_vector(
        vector=[0.0, 1.0, 0.0, 0.0],
        text="Java is a programming language",
        metadata={
            "language": "java"
        },
        document_id="java"
    )

    store.save_vector(
        vector=[0.0, 0.0, 1.0, 0.0],
        text="Docker is a container platform",
        metadata={
            "technology": "docker"
        },
        document_id="docker"
    )

    results = store.search_vector(
        query_vector=[0.99, 0.01, 0.0, 0.0],
        top_k=3
    )

    assert len(results) == 3

    # Python should be the closest
    assert results[0]["id"] == "python"

    assert results[0]["text"] == (
        "Python is a programming language"
    )

    assert results[0]["metadata"]["language"] == "python"


def test_top_k(store):

    vectors = [
        (
            [1.0, 0.0, 0.0, 0.0],
            "python"
        ),
        (
            [0.0, 1.0, 0.0, 0.0],
            "java"
        ),
        (
            [0.0, 0.0, 1.0, 0.0],
            "docker"
        ),
        (
            [0.0, 0.0, 0.0, 1.0],
            "react"
        ),
    ]

    for vector, document_id in vectors:

        store.save_vector(
            vector=vector,
            text=f"{document_id} document",
            metadata={
                "type": "test"
            },
            document_id=document_id
        )

    results = store.search_vector(
        query_vector=[1.0, 0.0, 0.0, 0.0],
        top_k=2
    )

    assert len(results) == 2

    assert results[0]["id"] == "python"


def test_persistence():

    collection_name = f"persistence_{uuid.uuid4().hex}"

    store = VectorStore(
        collection_name=collection_name,
        persist_directory=TEST_DB
    )

    vector = [1.0, 0.0, 0.0, 0.0]

    store.save_vector(
        vector=vector,
        text="Persistent document",
        metadata={
            "source": "test"
        },
        document_id="persistent_doc"
    )

    # Create a completely new VectorStore
    new_store = VectorStore(
        collection_name=collection_name,
        persist_directory=TEST_DB
    )

    results = new_store.search_vector(
        query_vector=vector,
        top_k=1
    )

    assert len(results) == 1

    assert results[0]["id"] == "persistent_doc"

    assert results[0]["text"] == "Persistent document"

    assert results[0]["metadata"]["source"] == "test"


def test_metadata(store):

    metadata = {
        "user_id": "user_123",
        "session_id": "session_456",
        "source": "chat"
    }

    store.save_vector(
        vector=[1.0, 0.0, 0.0, 0.0],
        text="Test document",
        metadata=metadata,
        document_id="doc_1"
    )

    result = store.collection.get(
        ids=["doc_1"]
    )

    assert len(result["ids"]) == 1

    saved_metadata = result["metadatas"][0]

    assert saved_metadata["user_id"] == "user_123"
    assert saved_metadata["session_id"] == "session_456"
    assert saved_metadata["source"] == "chat"