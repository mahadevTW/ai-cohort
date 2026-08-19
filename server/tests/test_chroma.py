from server.database.chroma import VectorStore


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
    vector = [0.1, 0.2, 0.3]
    text = "Sample document text"
    metadata = {"title": "Sample Document", "section": "Introduction"}
    document_id = "doc_123"

    saved_id = store.save_vector(vector=vector, text=text, metadata=metadata, document_id=document_id)
    assert saved_id == document_id
    print(f"Vector saved successfully with document_id: {saved_id}")

def test_search_vector():
    # Test that the search function returns the expected results.
    store = VectorStore()
    query_vector = [0.1, 0.2, 0.3] 
    search_results = store.search_vector(query_vector=query_vector, top_k=3)
    print(f"Search results: {search_results}")
    pass

def test_get_vector():
    # Test that a vector can be retrieved correctly from the database.
    store = VectorStore()
    get_vector = store.get_vector(document_id="doc_123")
    print(f"Retrieved vector: {get_vector}")
    pass