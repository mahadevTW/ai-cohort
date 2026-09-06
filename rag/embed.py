# function which calls chunking system, reads all the chunks
# calls the embedding model reads the embedding result
# save embedding result to vector store
import os
from server.database.chroma import VectorStore

from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")

def embed(text: str) -> list[float]:
    return model.encode(text).tolist()

from rag.chunker import chunk_all_documents
rag_path  = "./data/chroma_data"
def train_rag(base_directory: str):
    store = VectorStore(
        path=rag_path,
        collection_name="documents"
    )
    result = chunk_all_documents(base_directory)
    for r in result:
        embed_r = embed(r["content"])
        store.save_vector(id=r["id"],vector=embed_r,metadata={
            "section":r["section"],
            "sub_section":r["subsection"],
            "file":r["file"],
        }, text=r["content"]
        )

if __name__ == "__main__":
    base_directory = "./data/policies"
    train_rag(base_directory)

    

    