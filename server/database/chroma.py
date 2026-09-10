import chromadb
from sentence_transformers import SentenceTransformer
from database.retrieval import bm25_rank, reciprocal_rank_fusion

model = SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> list[float]:
    return model.encode(text).tolist()


class VectorStore:

    def __init__(
        self,
        collection_name="documents",
        persist_directory="./chroma_db"
    ):
        self.client = chromadb.PersistentClient(
            path=persist_directory
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )

    def save_vector(
        self,
        vector,
        text,
        metadata=None,
        document_id=None
    ):
        """
        Save a vector, document text and metadata.
        """

        if document_id is None:
            raise ValueError("document_id is required")

        data = {
            "ids": [document_id],
            "embeddings": [vector],
            "documents": [text],
        }

        # Chroma does not allow empty metadata {}
        if metadata:
            data["metadatas"] = [metadata]

        # Chunk IDs are deterministic, so rerunning ingestion refreshes changed
        # policy content instead of creating duplicates or failing on an ID clash.
        self.collection.upsert(**data)

        return document_id

    def search_vector(
        self,
        query_vector,
        top_k=5
    ):
        """
        Search for similar vectors.
        """

        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k
        )

        response = []

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            response.append({
                "id": ids[i],
                "text": documents[i],
                "metadata": metadatas[i],
                "distance": distances[i]
            })

        return response

    def hybrid_search(self, query: str, top_k: int = 3, candidate_k: int = 12):
        """Combine semantic and exact-term retrieval with reciprocal-rank fusion."""
        query_vector = embed(query)
        semantic_results = self.search_vector(query_vector=query_vector, top_k=candidate_k)
        stored = self.collection.get(include=["documents", "metadatas"])
        ids = stored.get("ids", [])
        documents = stored.get("documents", [])
        metadatas = stored.get("metadatas", [])
        document_map = {
            document_id: {"text": text, "metadata": metadata or {}}
            for document_id, text, metadata in zip(ids, documents, metadatas)
            if text
        }
        lexical_ids = bm25_rank(
            query,
            {document_id: record["text"] for document_id, record in document_map.items()},
            limit=candidate_k,
        )
        semantic_ids = [result["id"] for result in semantic_results]
        result_by_id = {result["id"]: result for result in semantic_results}
        fused_ids = reciprocal_rank_fusion(semantic_ids, lexical_ids, limit=top_k)

        return [
            {
                "id": document_id,
                "text": document_map[document_id]["text"],
                "metadata": document_map[document_id]["metadata"],
                "distance": result_by_id.get(document_id, {}).get("distance"),
                "retrieval": "hybrid",
            }
            for document_id in fused_ids
            if document_id in document_map
        ]


def search_vectors(query_vector, top_k=5):
    """Search the default document collection for vectors similar to a query.

    This convenience function keeps callers independent of ``VectorStore`` while
    reusing its existing search implementation.
    """
    return VectorStore().search_vector(query_vector=query_vector, top_k=top_k)


def hybrid_search(query: str, top_k: int = 3, candidate_k: int = 12):
    """Search policy chunks using both semantic similarity and BM25 keyword matches."""
    return VectorStore().hybrid_search(query, top_k=top_k, candidate_k=candidate_k)

if __name__ == "__main__":
    # Example usage
    store = VectorStore()
    text = "This is a sample document."
    vector = embed(text)
    document_id = "doc1"
    metadata = {"title": "Sample Document", "author": "John Doe"}

    # Save the vector
    store.save_vector(vector, text, metadata, document_id)

    # Search for similar vectors
    query_vector = embed("sample")
    results = store.search_vector(query_vector, top_k=3)
    print(results)
