import os
import sys

# Resolve project root.
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

sys.path.insert(0, PROJECT_ROOT)

from rag.query import search_chromadb, print_search_results


def test_query(query: str):
    """
    Execute a semantic search against ChromaDB.
    """

    print("\n")
    print("=" * 100)
    print("                    USER QUERY")
    print("=" * 100)

    print(query)

    results = search_chromadb(
        query=query,
        n_results=5,
    )

    print_search_results(results)

    return results


if __name__ == "__main__":

    user_query = input(
        "\n Enter your query here: "
    ).strip()

    test_query(user_query)