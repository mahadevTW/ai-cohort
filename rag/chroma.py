import os
import sys

# Resolve paths from the repository root.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Put the project root before this script's directory. This prevents the local
# rag/chromadb.py module from shadowing the installed chromadb package.
sys.path.insert(0, PROJECT_ROOT)

from server.openai_client import chunk_file
from rag.embedder import embed_chunks
from rag.chromadb import COLLECTION_NAME, print_records, store_chunks


def print_chunks(chunks):
    """
    Print chunks returned by the LLM chunking logic.
    """

    print("\n")
    print("=" * 100)
    print("                    CHUNKS RECEIVED FROM LLM")
    print("=" * 100)

    print(f"\nTotal chunks: {len(chunks)}\n")

    for index, chunk in enumerate(chunks, start=1):

        print(f"Chunk #{index}")
        print("-" * 100)

        print(f"Id: {chunk.get('Id', '')}")
        print(f"Section: {chunk.get('section', '')}")
        print(f"Subsection: {chunk.get('Subsection', '')}")

        print("\nContent:")
        print(chunk.get("Content", ""))

        print("\n" + "=" * 100)

    print("\n")


def main():

    file_path = os.path.join(
        PROJECT_ROOT,
        "data",
        "policies",
        "01-onboarding-policy.md"
    )

    print(f"Processing file: {file_path}")

    try:

        # ============================================================
        # 1. Chunk document using your existing LLM logic
        # ============================================================

        chunks = chunk_file(file_path)

        # Print exactly what we received from the LLM
        print_chunks(chunks)

        # ============================================================
        # 2. Generate embeddings
        # ============================================================

        print("Generating embeddings using all-MiniLM-L6-v2...")

        chunks = embed_chunks(chunks)

        print(f"Generated embeddings for {len(chunks)} chunks.")

        # ============================================================
        # 3. Store chunks in the shared ChromaDB collection
        # ============================================================

        collection = store_chunks(chunks, file_path)

        # ============================================================
        # 4. Final result
        # ============================================================

        print("\n")
        print("=" * 100)
        print("                    INGESTION COMPLETE")
        print("=" * 100)

        print(f"Collection: {COLLECTION_NAME}")
        print(f"Chunks processed: {len(chunks)}")
        print(f"Documents in ChromaDB: {collection.count()}")
        print("=" * 100)

        print_records()

    except Exception as e:

        print(f"\nError processing file: {e}")

        raise


if __name__ == "__main__":
    main()
