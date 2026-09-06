import chromadb
from typing import List, Dict, Any


class VectorStore:
    def __init__(self, path: str = "./data/chroma", collection_name: str = "documents"):
        client = chromadb.PersistentClient(path=path)

        self.collection = client.get_or_create_collection(
            name=collection_name
        )

    def save_vector(
        self,
        id: str,
        vector: List[float],
        metadata: Dict[str, Any],
        text = str
    ) -> None:
        """
        Save pre-computed vectors along with metadata.

        Example metadata:
        {
            "citation": "https://example.com/article",
            "title": "My Article",
            "page": 5
        }
        """

        if len(id) == 0 or len(vector) == 0 or not metadata:
            raise ValueError(
                "ids, vectors and metadatas must have the same length"
            )

        return self.collection.upsert(
                      ids=[id],
            embeddings=[vector],
            metadatas=[metadata],
            documents=[text]
        )

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search using a pre-computed query vector.

        Returns vectors and their metadata/citations.
        """

        result = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["embeddings", "metadatas", "distances"]
        )

        results = []

        for i in range(len(result["ids"][0])):
            results.append({
                "id": result["ids"][0][i],
                "vector": result["embeddings"][0][i],
                "metadata": result["metadatas"][0][i],
                "distance": result["distances"][0][i],
                "documents": results["documents"][0]
            })
        return results