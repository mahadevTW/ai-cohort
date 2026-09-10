from pathlib import Path

from chunker import chunk_markdown, chunker


def test_chunks_keep_markdown_heading_context():
    chunks = chunk_markdown(
        "policy.md",
        "# Access Policy\n\n## Section 1: Accounts\n\n### 1.1 MFA\nMFA is required.\n",
    )

    assert len(chunks) == 1
    assert chunks[0]["section"] == "Section 1: Accounts"
    assert chunks[0]["subsection"] == "1.1 MFA"
    assert "Policy: Access Policy" in chunks[0]["content"]
    assert "MFA is required." in chunks[0]["content"]


def test_chunk_ids_are_deterministic_and_large_content_is_split():
    content = "# Policy\n## Rules\n### Detail\n" + ("A complete rule. " * 200)
    first = chunk_markdown("policy.md", content, max_chunk_chars=300, overlap_chars=30)
    second = chunk_markdown("policy.md", content, max_chunk_chars=300, overlap_chars=30)

    assert len(first) > 1
    assert [chunk["document_id"] for chunk in first] == [chunk["document_id"] for chunk in second]
    assert all(chunk["section"] == "Rules" for chunk in first)


def test_all_policy_files_produce_contextual_chunks():
    policy_dir = Path(__file__).resolve().parents[2] / "data" / "policies"
    files = sorted(policy_dir.glob("[0-9][0-9]-*.md"))
    chunks = [chunk for path in files for chunk in chunker(policy_dir, path.name)]

    assert len(files) == 15
    assert len(chunks) == 485
    assert all(chunk["content"].startswith("Policy: ") for chunk in chunks)
    assert all(len(chunk["content"].partition("\n\n")[2]) <= 1_400 for chunk in chunks)
