"""Deterministic, Markdown-aware chunking for policy documents."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

DEFAULT_MAX_CHUNK_CHARS = 1_400
DEFAULT_OVERLAP_CHARS = 120
_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _normalise_heading(value: str) -> str:
    return value.strip().rstrip("#").strip()


def _with_overlap(previous: str, current: str, overlap_chars: int) -> str:
    if not previous or not overlap_chars:
        return current
    overlap = previous[-overlap_chars:]
    space = overlap.find(" ")
    if space >= 0:
        overlap = overlap[space + 1 :]
    return f"{overlap}\n\n{current}".strip()


def _split_text(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Split oversized content at paragraphs, then sentences, then hard boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    pieces: list[str] = []
    current = ""

    def add_unit(unit: str) -> None:
        nonlocal current
        candidate = f"{current}\n\n{unit}".strip() if current else unit
        if len(candidate) <= max_chars:
            current = candidate
        elif current:
            pieces.append(current)
            current = _with_overlap(current, unit, overlap_chars)
        else:
            current = unit

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            add_unit(paragraph)
            continue
        for sentence in (s.strip() for s in _SENTENCE_BOUNDARY.split(paragraph) if s.strip()):
            if len(sentence) <= max_chars:
                add_unit(sentence)
                continue
            if current:
                pieces.append(current)
                current = ""
            while len(sentence) > max_chars:
                pieces.append(sentence[:max_chars])
                sentence = _with_overlap(pieces[-1], sentence[max_chars:], overlap_chars)
            current = sentence
    if current:
        pieces.append(current)
    return pieces or [""]


def chunk_markdown(
    filename: str,
    content: str,
    *,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[dict[str, str]]:
    """Chunk a policy by its Markdown hierarchy, without an LLM call."""
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars cannot be negative")

    matches = list(_HEADING.finditer(content))
    policy = Path(filename).stem.replace("-", " ").title()
    for match in matches:
        if len(match.group(1)) == 1:
            policy = _normalise_heading(match.group(2))
            break

    units: list[tuple[str, str, str]] = []
    section = subsection = ""
    body_start = matches[0].end() if matches else 0

    def collect(end: int) -> None:
        body = content[body_start:end].strip()
        if body:
            # Policy metadata before the first ## heading is retrievable content too.
            units.append((section or "Document Information", subsection, body))

    for index, match in enumerate(matches):
        level = len(match.group(1))
        heading = _normalise_heading(match.group(2))
        if level == 1:
            body_start = match.end()
        elif level == 2:
            collect(match.start())
            section, subsection, body_start = heading, "", match.end()
        elif level == 3:
            collect(match.start())
            subsection, body_start = heading, match.end()

    collect(len(content))

    chunks: list[dict[str, str]] = []
    for section, subsection, body in units:
        context = f"Policy: {policy}\nSection: {section}"
        if subsection:
            context += f"\nSubsection: {subsection}"
        for part_index, part in enumerate(_split_text(body, max_chunk_chars, overlap_chars), start=1):
            document_id = hashlib.sha256(
                f"{filename}|{section}|{subsection}|{part_index}".encode("utf-8")
            ).hexdigest()
            chunks.append({
                "document_id": document_id,
                "filename": filename,
                "policy": policy,
                "section": section,
                "subsection": subsection,
                "content": f"{context}\n\n{part}".strip(),
            })
    return chunks


def chunker(directory_path: str | Path, filename: str) -> list[dict[str, str]]:
    """Chunk one Markdown policy without using an external service."""
    path = Path(directory_path) / filename
    if path.suffix.lower() != ".md":
        return []
    return chunk_markdown(path.name, path.read_text(encoding="utf-8"))
