#create a function embedding in file embed.py which will call chunker from chunker.py
#Also, it will make use of functions get_vector, save_vector, search_vectors from chroma.py to receive data from chuker to store in vectors and save it store and retrieve from chromadb

import os

from chunker import chunker
from database.chroma import VectorStore, embed

directory_path_tst = r"C:\AI_Learning\git\ai-cohort\data\policies"

def embedding(directory_path):
    chunks = []
    for filename in os.listdir(directory_path):
        if filename.endswith(".md"):
            # Call the openai_chunker function with the content of the directory and file
            print(f"Calling CHUNKER for file: {filename}")
            chunks = chunker(directory_path,filename=filename)
            print(f"Finished processing file: {filename}, generated {len(chunks)} chunks.")
        # Save each chunk as a vector in ChromaDB
    # 2. Save chunks + embeddings into ChromaDB
    store = VectorStore()
    for chunk in chunks:
        vector = embed(chunk["content"])
        store.save_vector(
            vector=vector,
            text=chunk["content"],
            metadata={"title": chunk["filename"], "section": chunk["section"]},
            document_id=chunk["document_id"],
        )

    print(f"Successfully embedded {len(chunks)} chunks.")

def search_my_vectors(search_text: str = "What is the Password Complexity and Length Rules policy?"):
    """Embed a query with the ingestion model and verify Chroma returns matches."""
    print(f"From search_my_vectors: 1. Embedding the search text: {search_text}")
    store = VectorStore()
    query_vector = embed(search_text)

    # The current VectorStore API is named search_vector (singular).
    search_results = store.search_vector(query_vector=query_vector, top_k=3)
    print(f"From search_my_vectors: 2")
    assert search_results, "Expected at least one matching document in ChromaDB"
    assert all(result["id"] and result["text"] for result in search_results)
    print(f"From search_my_vectors: 3. Search results: {search_results}")
    # for index, result in enumerate(search_results, start=1):
    #     print(f"\nResult {index}")
    #     print(f"File: {result['metadata'].get('title', 'Unknown')}")
    #     #print(f"Section: {result['metadata'].get('section', 'Unknown')}")
    #     print(f"Distance: {result['distance']:.4f}")
    #     print(f"Text: {result['text']}")

if __name__ == "__main__":
    # Example usage
    #embedding(directory_path_tst)
    search_my_vectors (search_text="What is the Password Complexity and Length Rules policy?")
    print(f"From Main: Total chunks generated and saved") 