import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chunker import chunk_document, read_file
from database.chroma import VectorStore, embed


def embed_file(file_path: str):
    """
    Read a file, chunk its content, generate embeddings,
    and save the vectors to ChromaDB.
    """

    # 1. Chunk the text
    chunks = chunk_document(file_path)

    if not chunks:
        raise ValueError("No chunks generated from the file.")

    # 2. Save chunks + embeddings into ChromaDB
    store = VectorStore()
    for chunk in chunks:
        vector = embed(chunk["content"])
        store.save_vector(
            vector=vector,
            text=chunk["content"],
            metadata={"title": chunk["title"], "section": chunk["section"]},
            document_id=chunk["id"],
        )

    print(f"Successfully embedded {len(chunks)} chunks.")


if __name__ == "__main__":
    policies_dir = Path(r"C:\Users\Admin\projects\ai-cohort\data\policies")

    for file_path in sorted(policies_dir.iterdir()):
        if file_path.is_file():
            print(f"Embedding: {file_path.name}")
            embed_file(str(file_path))