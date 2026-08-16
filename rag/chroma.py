import chromadb

import os
import sys

# Resolve paths from the repository root so this script works regardless of
# the directory from which it is launched.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from server.openai_client import chunk_file


def main():
    file_path = os.path.join(
        PROJECT_ROOT,
        "data",
        "policies",
        "01-onboarding-policy.md"
    )

    print(f"Processing file: {file_path}")

    try:
        chunks = chunk_file(file_path)

        print("\n========== CHUNKS ==========\n")

        for chunk in chunks:
            print(f"Id: {chunk['Id']}")
            print(f"section: {chunk['section']}")
            print(f"Subsection: {chunk['Subsection']}")
            print(f"Content: {chunk['Content']}")
            print("\n" + "=" * 80 + "\n")

    except Exception as e:
        print(f"Error processing file: {e}")
        raise


if __name__ == "__main__":
    main()
