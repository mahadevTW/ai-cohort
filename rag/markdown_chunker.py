"""
markdown_chunker.py

Structure-aware Markdown chunker for policy documents.

Features:
- Parses Markdown headings (#, ##, ### ...)
- Treats each subsection (###) as the primary chunk
- Preserves document/section/subsection hierarchy
- Extracts document-level metadata
- Adds enriched metadata and searchable text
- Creates FAQ chunks separately
- Splits unusually long subsections without breaking paragraphs
- Returns dictionaries that can be directly stored in ChromaDB

Usage:
    from markdown_chunker import chunk_file

    chunks = chunk_file("data/policies/01-onboarding-policy.md")

    for chunk in chunks:
        print(chunk["Id"])
        print(chunk["Section"])
        print(chunk["Subsection"])
        print(chunk["Content"])
        print(chunk["Metadata"])
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MAX_CHARS = 4000
DEFAULT_OVERLAP_CHARS = 400

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# Matches both "**Key:** Value" and "**Key**: Value" metadata formats.
KEY_VALUE_RE = re.compile(r"^\*\*(.+?)\*\*:?\s*(.+?)\s*$")

FAQ_QUESTION_RE = re.compile(
    r"^\*\*Q:\s*(.+?)\*\*\s*$",
    re.IGNORECASE,
)

FAQ_ANSWER_RE = re.compile(
    r"^A:\s*(.+?)\s*$",
    re.IGNORECASE,
)

NUMBERED_SECTION_RE = re.compile(
    r"^Section\s+(\d+)\s*:\s*(.+)$",
    re.IGNORECASE,
)

NUMBERED_SUBSECTION_RE = re.compile(
    r"^(\d+(?:\.\d+)*)\s+(.+)$"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_file(
    file_path: str | Path,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> List[Dict[str, Any]]:
    """
    Read a Markdown policy document and return structure-aware chunks.

    Primary chunk boundary:
        ### subsection

    Special handling:
        - Document metadata is extracted from **Key:** Value lines.
        - ## sections are used as parent context.
        - ### subsections become individual chunks.
        - FAQ question/answer pairs become individual FAQ chunks.
        - Long subsections are split into smaller chunks.
        - Each chunk receives enriched metadata.

    Args:
        file_path: Markdown file path.
        max_chars: Maximum approximate character length for a chunk.
        overlap_chars: Overlap used when a long subsection must be split.

    Returns:
        List of dictionaries with:
            Id
            Section
            Subsection
            Content
            Metadata
            EmbeddingText
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")

    if not path.is_file():
        raise ValueError(f"Expected a file but received: {path}")

    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0")

    if overlap_chars < 0:
        raise ValueError("overlap_chars cannot be negative")

    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    text = path.read_text(encoding="utf-8")

    return chunk_markdown(
        text=text,
        source_path=path,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )


def chunk_markdown(
    text: str,
    source_path: Optional[Path] = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> List[Dict[str, Any]]:
    """
    Chunk Markdown text without requiring a file on disk.
    """
    lines = _normalize_lines(text)

    document_metadata = _extract_document_metadata(lines)
    document_title = _extract_document_title(lines)

    sections = _parse_sections(lines)

    chunks: List[Dict[str, Any]] = []

    for section_index, section in enumerate(sections, start=1):
        section_number = section["number"]
        section_title = section["title"]

        # Fall back to a positional identifier when the heading does not
        # carry an explicit "Section N" number, so sections with identical
        # (empty) numbers don't collide in generated chunk IDs.
        section_id_part = section_number or f"s{section_index}"

        # If the section contains explicit subsections, chunk by subsection.
        if section["subsections"]:
            for subsection_index, subsection in enumerate(
                section["subsections"], start=1
            ):
                subsection_chunks = _create_subsection_chunks(
                    subsection=subsection,
                    section_number=section_id_part,
                    section_title=section_title,
                    document_title=document_title,
                    document_metadata=document_metadata,
                    source_path=source_path,
                    max_chars=max_chars,
                    overlap_chars=overlap_chars,
                    subsection_index=subsection_index,
                )
                chunks.extend(subsection_chunks)

        # A section without ### subsections should still be retrievable.
        elif "\n".join(section["content"]).strip():
            content = "\n".join(section["content"]).strip()

            for part_index, part in enumerate(
                _split_long_text(content, max_chars, overlap_chars),
                start=1,
            ):
                chunks.append(
                    _build_chunk(
                        chunk_id=_make_chunk_id(
                            document_metadata,
                            section_id_part,
                            "section",
                            part_index,
                        ),
                        document_title=document_title,
                        document_metadata=document_metadata,
                        section_number=section_number,
                        section_title=section_title,
                        subsection_number="",
                        subsection_title="",
                        content=part,
                        chunk_type="section",
                        source_path=source_path,
                        part_index=part_index,
                    )
                )

    # If the document has no ## sections, create document-level chunks.
    if not chunks:
        body = "\n".join(lines).strip()

        if body:
            for part_index, part in enumerate(
                _split_long_text(body, max_chars, overlap_chars),
                start=1,
            ):
                chunks.append(
                    _build_chunk(
                        chunk_id=_make_chunk_id(
                            document_metadata,
                            "document",
                            "document",
                            part_index,
                        ),
                        document_title=document_title,
                        document_metadata=document_metadata,
                        section_number="",
                        section_title="",
                        subsection_number="",
                        subsection_title="",
                        content=part,
                        chunk_type="document",
                        source_path=source_path,
                        part_index=part_index,
                    )
                )

    return chunks


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

def _normalize_lines(text: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")

    # Remove excessive blank lines while preserving paragraph boundaries.
    normalized: List[str] = []

    previous_blank = False

    for line in lines:
        line = line.rstrip()

        if not line.strip():
            if not previous_blank:
                normalized.append("")
            previous_blank = True
        else:
            normalized.append(line)
            previous_blank = False

    return normalized


def _extract_document_title(lines: List[str]) -> str:
    for line in lines:
        match = HEADING_RE.match(line)

        if match and len(match.group(1)) == 1:
            return match.group(2).strip()

    return ""


def _extract_document_metadata(lines: List[str]) -> Dict[str, str]:
    """
    Extract metadata such as:

        **Document ID:** ONB-101
        **Version:** 1.4
        **Effective Date:** March 3, 2025
        **Owner:** Human Resources
    """
    metadata: Dict[str, str] = {}

    for line in lines:
        match = KEY_VALUE_RE.match(line.strip())

        if not match:
            continue

        key = _normalize_metadata_key(match.group(1).rstrip(":"))
        value = match.group(2).strip()

        metadata[key] = value

    return metadata


def _normalize_metadata_key(key: str) -> str:
    key = key.strip().lower()

    key = re.sub(r"[^a-z0-9]+", "_", key)
    key = re.sub(r"_+", "_", key)

    return key.strip("_")


def _parse_sections(lines: List[str]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []

    current_section: Optional[Dict[str, Any]] = None
    current_subsection: Optional[Dict[str, Any]] = None

    for line in lines:
        heading = HEADING_RE.match(line)

        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()

            if level == 2:
                current_section = {
                    "number": _extract_section_number(title),
                    "title": _clean_section_title(title),
                    "content": [],
                    "subsections": [],
                }

                sections.append(current_section)
                current_subsection = None

            elif level == 3:
                if current_section is None:
                    # Create an implicit section if malformed Markdown
                    # contains a ### before any ## heading.
                    current_section = {
                        "number": "",
                        "title": "",
                        "content": [],
                        "subsections": [],
                    }
                    sections.append(current_section)

                subsection = {
                    "number": _extract_subsection_number(title),
                    "title": _clean_subsection_title(title),
                    "content": [],
                }

                current_section["subsections"].append(subsection)
                current_subsection = subsection

            else:
                # Deeper headings remain part of the current subsection.
                target = (
                    current_subsection["content"]
                    if current_subsection is not None
                    else (
                        current_section["content"]
                        if current_section is not None
                        else []
                    )
                )

                target.append(line)

            continue

        if current_subsection is not None:
            current_subsection["content"].append(line)

        elif current_section is not None:
            current_section["content"].append(line)

    return sections


def _extract_section_number(title: str) -> str:
    match = NUMBERED_SECTION_RE.match(title)

    if match:
        return match.group(1)

    return ""


def _clean_section_title(title: str) -> str:
    match = NUMBERED_SECTION_RE.match(title)

    if match:
        return match.group(2).strip()

    return title.strip()


def _extract_subsection_number(title: str) -> str:
    match = NUMBERED_SUBSECTION_RE.match(title)

    if match:
        return match.group(1)

    return ""


def _clean_subsection_title(title: str) -> str:
    match = NUMBERED_SUBSECTION_RE.match(title)

    if match:
        return match.group(2).strip()

    return title.strip()


# ---------------------------------------------------------------------------
# Chunk creation
# ---------------------------------------------------------------------------

def _create_subsection_chunks(
    subsection: Dict[str, Any],
    section_number: str,
    section_title: str,
    document_title: str,
    document_metadata: Dict[str, str],
    source_path: Optional[Path],
    max_chars: int,
    overlap_chars: int,
    subsection_index: int = 1,
) -> List[Dict[str, Any]]:

    content = "\n".join(subsection["content"]).strip()

    if not content:
        return []

    parts = _split_long_text(
        content,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )

    chunks: List[Dict[str, Any]] = []

    # Fall back to a positional identifier when the subsection heading
    # does not carry an explicit number, avoiding ID collisions between
    # multiple unnumbered subsections within the same section.
    subsection_id_part = subsection["number"] or f"sub{subsection_index}"

    for part_index, part in enumerate(parts, start=1):
        chunks.append(
            _build_chunk(
                chunk_id=_make_chunk_id(
                    document_metadata,
                    section_number or "section",
                    subsection_id_part,
                    part_index,
                ),
                document_title=document_title,
                document_metadata=document_metadata,
                section_number=section_number,
                section_title=section_title,
                subsection_number=subsection["number"],
                subsection_title=subsection["title"],
                content=part,
                chunk_type="policy",
                source_path=source_path,
                part_index=part_index,
            )
        )

    return chunks


def _build_chunk(
    chunk_id: str,
    document_title: str,
    document_metadata: Dict[str, str],
    section_number: str,
    section_title: str,
    subsection_number: str,
    subsection_title: str,
    content: str,
    chunk_type: str,
    source_path: Optional[Path],
    part_index: int,
) -> Dict[str, Any]:

    metadata = _build_metadata(
        document_title=document_title,
        document_metadata=document_metadata,
        section_number=section_number,
        section_title=section_title,
        subsection_number=subsection_number,
        subsection_title=subsection_title,
        content=content,
        chunk_type=chunk_type,
        source_path=source_path,
        part_index=part_index,
    )

    embedding_text = _build_embedding_text(
        document_title=document_title,
        document_metadata=document_metadata,
        section_number=section_number,
        section_title=section_title,
        subsection_number=subsection_number,
        subsection_title=subsection_title,
        content=content,
        metadata=metadata,
    )

    return {
        # Existing-style fields for compatibility with a typical
        # chunk_file() consumer.
        "Id": chunk_id,
        "Section": section_title,
        "Subsection": subsection_title,
        "Content": content,

        # New enriched fields.
        "Metadata": metadata,
        "EmbeddingText": embedding_text,

        # Lowercase aliases are convenient for ChromaDB / APIs.
        "id": chunk_id,
        "content": content,
        "metadata": metadata,
        "embedding_text": embedding_text,
    }


# ---------------------------------------------------------------------------
# Metadata enrichment
# ---------------------------------------------------------------------------

def _build_metadata(
    document_title: str,
    document_metadata: Dict[str, str],
    section_number: str,
    section_title: str,
    subsection_number: str,
    subsection_title: str,
    content: str,
    chunk_type: str,
    source_path: Optional[Path],
    part_index: int,
) -> Dict[str, Any]:

    metadata: Dict[str, Any] = {}

    # Document-level metadata
    metadata.update(document_metadata)

    # Hierarchical metadata
    metadata.update(
        {
            "document_title": document_title,
            "section_number": section_number,
            "section_title": section_title,
            "subsection_number": subsection_number,
            "subsection_title": subsection_title,
            "chunk_type": chunk_type,
            "part_index": part_index,
        }
    )

    if source_path is not None:
        # Convert Path to str. This is important because ChromaDB does
        # not accept pathlib.Path as a metadata value.
        metadata["source_file"] = str(source_path)

        metadata["source_filename"] = source_path.name

    # Extract useful retrieval signals.
    metadata["keywords"] = _extract_keywords(
        section_title=section_title,
        subsection_title=subsection_title,
        content=content,
    )

    metadata["systems"] = _extract_systems(content)
    metadata["queues"] = _extract_queues(content)
    metadata["ticket_priorities"] = _extract_ticket_priorities(content)
    metadata["timelines"] = _extract_timelines(content)
    metadata["references"] = _extract_policy_references(content)

    # Ensure all metadata values are ChromaDB-safe.
    return _sanitize_metadata(metadata)


def _extract_keywords(
    section_title: str,
    subsection_title: str,
    content: str,
) -> List[str]:

    text = f"{section_title} {subsection_title} {content}"

    candidates = set()

    # Important policy/system terms.
    patterns = [
        r"\b(?:Workday|Greenhouse|Okta|Slack|ServiceDesk|Cornerstone)\b",
        r"\b(?:AWS|Salesforce|Figma|GitHub|Jira|Confluence)\b",
        r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b",
        r"\b(?:onboarding|pre-boarding|probation|equipment|access|"
        r"training|orientation|background verification|shipping|"
        r"acknowledgement|escalation|exception|compliance)\b",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            if isinstance(match, tuple):
                candidates.update(match)
            else:
                candidates.add(match)

    # Add meaningful words from headings.
    for word in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", subsection_title):
        candidates.add(word)

    return sorted(
        {
            str(item).strip()
            for item in candidates
            if str(item).strip()
        },
        key=str.lower,
    )


def _extract_systems(content: str) -> List[str]:
    known_systems = [
        "Workday",
        "Greenhouse",
        "Okta",
        "Slack",
        "Creatics ServiceDesk",
        "Cornerstone",
        "GitHub",
        "Jira",
        "Salesforce",
        "AWS",
        "Figma",
        "Confluence",
    ]

    return [
        system
        for system in known_systems
        if re.search(re.escape(system), content, re.IGNORECASE)
    ]


def _extract_queues(content: str) -> List[str]:
    return sorted(
        set(
            re.findall(
                r"(?:queue:\s*`([^`]+)`|queue\s+`([^`]+)`)",
                content,
                flags=re.IGNORECASE,
            )
        )
    )


def _extract_ticket_priorities(content: str) -> List[str]:
    return sorted(
        set(
            re.findall(
                r"\bP[0-9]\b",
                content,
                flags=re.IGNORECASE,
            )
        )
    )


def _extract_timelines(content: str) -> List[str]:
    patterns = [
        r"\b\d+\s+(?:business|calendar)\s+days?\b",
        r"\b\d+\s+(?:business|calendar)\s+weeks?\b",
        r"\b\d+\s+(?:business|calendar)\s+hours?\b",
        r"\b\d+\s+days?\b",
        r"\b\d+\s+hours?\b",
        r"\b\d+\s+weeks?\b",
    ]

    values = set()

    for pattern in patterns:
        values.update(
            re.findall(
                pattern,
                content,
                flags=re.IGNORECASE,
            )
        )

    return sorted(values, key=str.lower)


def _extract_policy_references(content: str) -> List[str]:
    # Examples: VEN-100, AST-100, PWD-100, ONB-101
    return sorted(
        set(
            re.findall(
                r"\b[A-Z]{2,10}-\d{2,5}\b",
                content,
            )
        )
    )


def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure metadata is compatible with ChromaDB.

    Supported:
        str
        int
        float
        bool
        list
        None

    pathlib.Path is converted to str.
    """

    sanitized: Dict[str, Any] = {}

    for key, value in metadata.items():

        if isinstance(value, Path):
            sanitized[key] = str(value)

        elif isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value

        elif isinstance(value, list):
            sanitized[key] = [
                str(item) if isinstance(item, Path) else item
                for item in value
            ]

        else:
            sanitized[key] = str(value)

    return sanitized


# ---------------------------------------------------------------------------
# Embedding text
# ---------------------------------------------------------------------------

def _build_embedding_text(
    document_title: str,
    document_metadata: Dict[str, str],
    section_number: str,
    section_title: str,
    subsection_number: str,
    subsection_title: str,
    content: str,
    metadata: Dict[str, Any],
) -> str:

    lines = [
        f"Document: {document_title}",
    ]

    document_id = document_metadata.get("document_id")

    if document_id:
        lines.append(f"Document ID: {document_id}")

    version = document_metadata.get("version")

    if version:
        lines.append(f"Version: {version}")

    if section_number or section_title:
        lines.append(
            f"Section: {section_number} {section_title}".strip()
        )

    if subsection_number or subsection_title:
        lines.append(
            f"Subsection: {subsection_number} {subsection_title}".strip()
        )

    keywords = metadata.get("keywords", [])

    if keywords:
        lines.append(
            "Keywords: " + ", ".join(str(k) for k in keywords)
        )

    systems = metadata.get("systems", [])

    if systems:
        lines.append(
            "Systems: " + ", ".join(str(s) for s in systems)
        )

    queues = metadata.get("queues", [])

    if queues:
        lines.append(
            "Queues: " + ", ".join(str(q) for q in queues)
        )

    timelines = metadata.get("timelines", [])

    if timelines:
        lines.append(
            "Timelines: " + ", ".join(str(t) for t in timelines)
        )

    references = metadata.get("references", [])

    if references:
        lines.append(
            "Policy References: " + ", ".join(str(r) for r in references)
        )

    lines.extend(
        [
            "",
            "Content:",
            content.strip(),
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Long-text splitting
# ---------------------------------------------------------------------------

def _split_long_text(
    text: str,
    max_chars: int,
    overlap_chars: int,
) -> List[str]:

    text = text.strip()

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    # First try paragraph boundaries.
    paragraphs = re.split(r"\n\s*\n", text)

    chunks: List[str] = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        candidate = (
            paragraph
            if not current
            else current + "\n\n" + paragraph
        )

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            # A single paragraph is too long; split by sentences/words.
            sentence_parts = _split_by_sentences(
                paragraph,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )
            chunks.extend(sentence_parts)

    if current:
        chunks.append(current)

    return chunks


def _split_by_sentences(
    text: str,
    max_chars: int,
    overlap_chars: int,
) -> List[str]:

    sentences = re.split(
        r"(?<=[.!?])\s+",
        text,
    )

    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        candidate = (
            sentence
            if not current
            else current + " " + sentence
        )

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            chunks.append(current)

            overlap = current[-overlap_chars:] if overlap_chars else ""
            current = overlap.strip()

        # If one sentence itself is bigger than max_chars,
        # split it by words as the final fallback.
        if len(sentence) > max_chars:
            word_chunks = _split_by_words(
                sentence,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )

            if current:
                word_chunks[0] = (
                    current + " " + word_chunks[0]
                ).strip()

            chunks.extend(word_chunks[:-1])
            current = word_chunks[-1]

        else:
            current = (
                sentence
                if not current
                else current + " " + sentence
            )

    if current:
        chunks.append(current)

    return chunks


def _split_by_words(
    text: str,
    max_chars: int,
    overlap_chars: int,
) -> List[str]:

    words = text.split()

    chunks: List[str] = []
    current_words: List[str] = []

    for word in words:
        candidate = " ".join(current_words + [word])

        if len(candidate) <= max_chars:
            current_words.append(word)
            continue

        if current_words:
            current = " ".join(current_words)
            chunks.append(current)

            if overlap_chars:
                overlap_words: List[str] = []
                overlap_length = 0

                for previous_word in reversed(current_words):
                    if overlap_length + len(previous_word) + 1 > overlap_chars:
                        break

                    overlap_words.insert(0, previous_word)
                    overlap_length += len(previous_word) + 1

                current_words = overlap_words
            else:
                current_words = []

        current_words.append(word)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------

def _make_chunk_id(
    document_metadata: Dict[str, str],
    section_number: str,
    subsection_number: str,
    part_index: int,
) -> str:

    document_id = document_metadata.get("document_id", "DOC")

    safe_document_id = _safe_id(document_id)
    safe_section = _safe_id(section_number or "section")
    safe_subsection = _safe_id(subsection_number or "content")

    return (
        f"{safe_document_id}_"
        f"{safe_section}_"
        f"{safe_subsection}_"
        f"{part_index}"
    )


def _safe_id(value: str) -> str:
    value = str(value).strip()

    value = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        value,
    )

    return value.strip("_") or "unknown"


# ---------------------------------------------------------------------------
# Simple standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Structure-aware Markdown policy chunker"
    )

    parser.add_argument(
        "file",
        help="Path to Markdown policy file",
    )

    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help="Maximum characters per chunk",
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=DEFAULT_OVERLAP_CHARS,
        help="Overlap for long chunks",
    )

    args = parser.parse_args()

    chunks = chunk_file(
        args.file,
        max_chars=args.max_chars,
        overlap_chars=args.overlap,
    )

    print(f"\nTotal chunks: {len(chunks)}\n")

    for chunk in chunks:
        print("=" * 80)
        print(f"ID          : {chunk['Id']}")
        print(f"Section     : {chunk['Section']}")
        print(f"Subsection  : {chunk['Subsection']}")
        print(f"Chunk Type  : {chunk['Metadata']['chunk_type']}")
        print(f"Keywords    : {chunk['Metadata']['keywords']}")
        print(f"Systems     : {chunk['Metadata']['systems']}")
        print(f"Queues      : {chunk['Metadata']['queues']}")
        print(f"Timelines   : {chunk['Metadata']['timelines']}")
        print("-" * 80)
        print(chunk["Content"])
        print("=" * 80)
