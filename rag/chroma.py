import os 
import sys 
from pathlib import Path
 
# Resolve paths from the repository root. 
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
# Put the project root before this script's directory. This prevents the local 
# rag/chromadb.py module from shadowing the installed chromadb package. 
sys.path.insert(0, PROJECT_ROOT) 
 
from rag.markdown_chunker import chunk_file
from rag.embedder import embed_chunks 
from rag.chromadb import COLLECTION_NAME, print_records, store_chunks, print_vectors 
 
 
def print_chunks(chunks): 
   for chunk in chunks:
    print(chunk["Id"])
    print(chunk["Section"])
    print(chunk["Subsection"])
    print(chunk["Content"])
    print(chunk["Metadata"])
 
 
def main(): 
     
    policies_dir = Path(PROJECT_ROOT) / "data" / "allpolicies"
 
    for file_path in sorted(policies_dir.iterdir()): 
        if file_path.is_file(): 
            print(f"Embedding: {file_path.name}") 
         
        print(f"Processing file: {file_path}") 
 
        try: 
 
            # ============================================================ 
            # 1. Chunk document using chunk_file logic 
            # ============================================================ 
 
            chunks = chunk_file(str(file_path)) 
 
            # Print exactly what we received from the LLM 
            print_chunks(chunks) 
 
            # ============================================================ 
            # 2. Generate embeddings 
            # ============================================================ 
 
            print("Generating embeddings using all-MiniLM-L6-v2...") 
 
            embeddings  = embed_chunks(chunks) 
 
            print(f"Generated embeddings for {len(chunks)} chunks.") 
            
            for chunk, embedding in zip(chunks, embeddings):
                print("=" * 80)
                print("ID:", chunk["Id"])
                print("Section:", chunk["Section"])
                print("Subsection:", chunk["Subsection"])

                print("\nContent:")
                print(chunk["Content"])

                print("\nEmbedding text:")
                print(chunk["EmbeddingText"])

                print("\nEmbedding dimensions:")
                print(len(embedding))
            
 
            # ============================================================ 
            # 3. Store chunks in the shared ChromaDB collection 
            # ============================================================ 
 
            collection = store_chunks(chunks, str(file_path)) 
 
            # ============================================================ 
            # 4. Final result 
            # ============================================================ 
            # print("\n") 
            # print("=" * 100) 
            # print("                    INGESTION COMPLETE") 
            # print("=" * 100) 
            # print(f"Collection: {COLLECTION_NAME}") 
            # print(f"Chunks processed: {len(chunks)}") 
            # print(f"Documents in ChromaDB: {collection.count()}") 
            # print("=" * 100) 
            # print_records() 
            # print_vectors()
 
        except Exception as e: 
 
            print(f"\nError processing file: {e}") 
 
            raise 
 
 
if __name__ == "__main__": 
    main()