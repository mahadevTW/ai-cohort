from server.database.chroma import VectorStore

from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text: str) -> list[float]:
    return model.encode(text).tolist()

def test_semantic_search():
    store = VectorStore(
        path="./data/test_chroma",
        collection_name="test_documents"
    )

    documents = [
        {
            "id": "doc-1",
            "text": (
                "Python is a popular programming language used "
                "for AI, machine learning, and data science."
            ),
            "citation": "python-introduction.pdf"
        },
        {
            "id": "doc-2",
            "text": (
                "Chroma is a vector database designed for storing "
                "and searching embeddings for AI applications."
            ),
            "citation": "chroma-guide.pdf"
        },
        {
            "id": "doc-3",
            "text": (
                "Mumbai is one of the largest cities in India "
                "and is located on the country's western coast."
            ),
            "citation": "india-geography.pdf"
        }
    ]

    # Store documents
    for document in documents:
        vector = embed(document["text"])

        store.save_vector(
            id=document["id"],
            vector=vector,
            metadata={
                "text": document["text"],
                "citation": document["citation"]
            }
        )

    # Completely different text from the stored documents
    question = (
        "What database can I use to search embeddings "
        "for an AI application?"
    )

    query_vector = embed(question)

    results = store.search(
        query_vector=query_vector,
        top_k=3
    )

    # Make sure we got results
    assert len(results) == 3

    # The Chroma document should be the most relevant
    assert results[0]["id"] == "doc-2"

    # Make sure citation came back
    assert (
        results[0]["metadata"]["citation"]
        == "chroma-guide.pdf"
    )

    print("\nSemantic search results:")

    for result in results:
        print(
            f"{result['id']} | "
            f"distance={result['distance']:.4f} | "
            f"citation={result['metadata']['citation']}"
        )