import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai_client import chunk_file


def read_file(file_path: str) -> str:
    """
    Read text from a file.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    return path.read_text(encoding="utf-8")


def chunk_document(file_path: str) -> list[dict]:
    """
    Read a file and generate semantic chunks using OpenAI.
    """

    # Read file
    data = read_file(file_path)

    # Send file content to OpenAI
    chunks = chunk_file(data)

    title = Path(file_path).name

    result = []

    for chunk in chunks:
        result.append({
            "id": str(uuid.uuid4()),
            "title": title,
            "section": chunk["section"],
            "content": chunk["content"],
        })

    print(
        f"Chunking successful, "
        f"input size: {len(data)}, "
        f"chunks: {len(result)}"
    )

    return result