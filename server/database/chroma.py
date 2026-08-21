import chromadb
from sentence_transformers import SentenceTransformer

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

        self.collection.add(**data)

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


def search_vectors(query_vector, top_k=5):
    """Search the default document collection for vectors similar to a query.

    This convenience function keeps callers independent of ``VectorStore`` while
    reusing its existing search implementation.
    """
    return VectorStore().search_vector(query_vector=query_vector, top_k=top_k)

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
