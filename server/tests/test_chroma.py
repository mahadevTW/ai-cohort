from database.chroma import VectorStore, embed
from uuid import uuid4


system_messages = """I want to write a test case file test_chroma.py
It will have test cases for the functions in chroma.py file. It will test the following functions:
1. save_vector: Test that a vector is saved correctly in the database.
2. search_vector: Test that the search function returns the expected results.
3. get_vector: Test that a vector can be retrieved correctly from the database.
It will use pytest framework for writing the test cases.
"""

def test_save_vector():
    # Test that a vector is saved correctly in the database.
    store = VectorStore()
    text = "Sample document text"
    # Use the same 384-dimensional model as the vectors already in Chroma.
    vector = embed(text)
    metadata = {"title": "Sample Document", "section": "Introduction"}
    document_id = str(uuid4())

    saved_id = store.save_vector(vector=vector, text=text, metadata=metadata, document_id=document_id)
    assert saved_id == document_id
    print(f"Vector saved successfully with document_id: {saved_id}")

def test_search_vectors(search_text: str = "What is the Password Complexity and Length Rules policy?"):
    """Embed a query with the ingestion model and verify Chroma returns matches."""
    print(f"From test_search_vectors: 1. Embedding the search text: {search_text}")
    store = VectorStore()
    query_vector = embed(search_text)

    # The current VectorStore API is named search_vector (singular).
    search_results = store.search_vector(query_vector=query_vector, top_k=5)
    print(f"From test_search_vectors: 2")
    assert search_results, "Expected at least one matching document in ChromaDB"
    assert all(result["id"] and result["text"] for result in search_results)
    print(f"From test_search_vectors: 3. Search results: {search_results}")
    for index, result in enumerate(search_results, start=1):
        print(f"\nResult {index}")
        print(f"File: {result['metadata'].get('title', 'Unknown')}")
        #print(f"Section: {result['metadata'].get('section', 'Unknown')}")
        print(f"Distance: {result['distance']:.4f}")
        print(f"Text: {result['text']}")

    if __name__ == "__main__":
    # Example usage
        test_save_vector()
        test_search_vectors()
    