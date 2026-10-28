"""Text chunking module for Internal Company Knowledge Assistant.

Splits extracted document sections into overlapping, semantically coherent text chunks
while preserving document IDs, page numbers, section headings, and pricing conditions.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import List, Optional

from backend.document_processor import ExtractedSection, normalize_whitespace

DEFAULT_CHUNK_SIZE_WORDS = 500
DEFAULT_CHUNK_OVERLAP_WORDS = 75


@dataclass
class TextChunk:
    """A searchable chunk of text associated with its source document and location."""
    chunk_id: str
    document_id: str
    chunk_index: int
    chunk_text: str
    page_number: Optional[int]
    section_heading: Optional[str]
    word_count: int


def split_paragraph_into_sentences(text: str) -> List[str]:
    """Split text into sentences using regex boundary matching."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_section(
    section: ExtractedSection,
    document_id: str,
    starting_index: int,
    target_words: int = DEFAULT_CHUNK_SIZE_WORDS,
    overlap_words: int = DEFAULT_CHUNK_OVERLAP_WORDS,
) -> List[TextChunk]:
    """Chunk a single ExtractedSection into one or more TextChunk instances.

    Args:
        section: ExtractedSection to chunk.
        document_id: Associated document identifier.
        starting_index: Starting index for numbering chunks.
        target_words: Target word limit per chunk (~500 words).
        overlap_words: Overlapping word count between consecutive chunks (~75 words).

    Returns:
        List[TextChunk]: Resulting chunks.
    """
    clean_text = normalize_whitespace(section.text)
    words = clean_text.split()
    total_words = len(words)

    # If the entire section is already within the target size, keep it whole
    if total_words <= target_words:
        chunk = TextChunk(
            chunk_id=f"{document_id}_c{starting_index}",
            document_id=document_id,
            chunk_index=starting_index,
            chunk_text=clean_text,
            page_number=section.page_number,
            section_heading=section.section_heading,
            word_count=total_words,
        )
        return [chunk]

    # Otherwise, split by paragraphs first to preserve semantic cohesion
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    if len(paragraphs) <= 1:
        # Fallback to sentence-level splitting if no distinct paragraphs
        paragraphs = split_paragraph_into_sentences(clean_text)

    chunks: List[TextChunk] = []
    current_chunk_words: List[str] = []
    current_index = starting_index

    for p in paragraphs:
        p_words = p.split()
        if not p_words:
            continue

        # If adding this paragraph exceeds target and we already have content:
        if len(current_chunk_words) + len(p_words) > target_words and current_chunk_words:
            chunk_body = " ".join(current_chunk_words)
            chunk = TextChunk(
                chunk_id=f"{document_id}_c{current_index}",
                document_id=document_id,
                chunk_index=current_index,
                chunk_text=chunk_body,
                page_number=section.page_number,
                section_heading=section.section_heading,
                word_count=len(current_chunk_words),
            )
            chunks.append(chunk)
            current_index += 1

            # Build overlap from the tail of current chunk
            if overlap_words > 0 and len(current_chunk_words) > overlap_words:
                overlap = current_chunk_words[-overlap_words:]
            else:
                overlap = current_chunk_words[:]

            current_chunk_words = overlap + p_words
        else:
            current_chunk_words.extend(p_words)

    # Final remaining words
    if current_chunk_words:
        chunk_body = " ".join(current_chunk_words)
        chunk = TextChunk(
            chunk_id=f"{document_id}_c{current_index}",
            document_id=document_id,
            chunk_index=current_index,
            chunk_text=chunk_body,
            page_number=section.page_number,
            section_heading=section.section_heading,
            word_count=len(current_chunk_words),
        )
        chunks.append(chunk)

    return chunks


def chunk_document_sections(
    sections: List[ExtractedSection],
    document_id: str,
    target_words: int = DEFAULT_CHUNK_SIZE_WORDS,
    overlap_words: int = DEFAULT_CHUNK_OVERLAP_WORDS,
) -> List[TextChunk]:
    """Chunk all extracted sections of a document into a sequential list of TextChunks.

    Args:
        sections: List of ExtractedSection objects.
        document_id: Unique document identifier.
        target_words: Chunk target size in words.
        overlap_words: Overlap in words.

    Returns:
        List[TextChunk]: Ordered list of chunks with unique indices.
    """
    all_chunks: List[TextChunk] = []
    chunk_index = 0

    for section in sections:
        section_chunks = chunk_section(
            section=section,
            document_id=document_id,
            starting_index=chunk_index,
            target_words=target_words,
            overlap_words=overlap_words,
        )
        all_chunks.extend(section_chunks)
        chunk_index += len(section_chunks)

    return all_chunks
