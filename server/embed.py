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
            print(f"Processed file: {filename}, generated {len(chunks)} chunks.")
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

if __name__ == "__main__":
    # Example usage
    embedding(directory_path_tst)
    print(f"Total chunks generated and saved") 