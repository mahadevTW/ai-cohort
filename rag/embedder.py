from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"

# Load the model once.
_model = SentenceTransformer(MODEL_NAME)


def embed_chunks(chunks):
    """
    Generate embeddings for the Content field of each chunk.

    The generated embedding is added to each chunk as:
        chunk["embedding"]
    """

    texts = [
        chunk["Content"]
        for chunk in chunks
    ]

    embeddings = _model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.tolist()

    return chunks