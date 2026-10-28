"""Citation service for Internal Company Knowledge Assistant.

Formats, validates, and secures verifiable source citations linking generated answers
directly to approved document titles, page numbers, sections, and exact supporting excerpts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.access_control import can_user_access_document
from backend.retriever import RetrievalResult


@dataclass
class Citation:
    """Verifiable source citation attached to an answer."""
    citation_id: str
    document_id: str
    document_title: str
    document_category: str
    classification: str
    page_number: Optional[int]
    section_heading: Optional[str]
    supporting_excerpt: str
    similarity_score: float

    def format_label(self) -> str:
        """Format a human-readable citation label."""
        parts = [self.document_title]
        if self.page_number is not None:
            parts.append(f"Page {self.page_number}")
        if self.section_heading and self.section_heading != "General":
            parts.append(f"Section: {self.section_heading}")
        return " — ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "document_category": self.document_category,
            "classification": self.classification,
            "page_number": self.page_number,
            "section_heading": self.section_heading,
            "supporting_excerpt": self.supporting_excerpt,
            "similarity_score": round(self.similarity_score, 4),
            "label": self.format_label(),
        }


def extract_key_excerpt(text: str, query: str, max_words: int = 55) -> str:
    """Extract the most relevant sentence or window from text that addresses the query.

    Args:
        text: Full chunk text.
        query: User question.
        max_words: Maximum words for excerpt.

    Returns:
        str: Concise highlighted excerpt.
    """
    if not text:
        return ""

    query_tokens = set(re.findall(r"\b\w{3,}\b", query.lower()))
    sentences = re.split(r"(?<=[.!?])\s+", text)

    best_sentence = ""
    best_score = -1

    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        s_words = set(re.findall(r"\b\w{3,}\b", s_clean.lower()))
        score = len(query_tokens.intersection(s_words))
        if score > best_score:
            best_score = score
            best_sentence = s_clean

    if not best_sentence:
        best_sentence = sentences[0] if sentences else text[:250]

    words = best_sentence.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "..."
    return best_sentence


def build_citations(
    retrieved_results: List[RetrievalResult],
    query: str,
    user: Dict[str, Any],
    db_path: Optional[str] = None,
) -> List[Citation]:
    """Generate authenticated, deduplicated citations from retrieved chunks.

    Args:
        retrieved_results: Ranked list of RetrievalResult objects.
        query: Original user question.
        user: Authenticated user making the request.
        db_path: Optional database path.

    Returns:
        List[Citation]: Verified citations.
    """
    citations: List[Citation] = []
    seen_locations = set()

    for i, res in enumerate(retrieved_results, start=1):
        # Strict security re-verification: Ensure user has access
        if not can_user_access_document(user, res.document_id, db_path=db_path):
            continue

        loc_key = (res.document_id, res.page_number, res.section_heading)
        if loc_key in seen_locations:
            continue
        seen_locations.add(loc_key)

        excerpt = extract_key_excerpt(res.chunk_text, query)

        cit = Citation(
            citation_id=f"cit_{i}_{res.document_id[:8]}",
            document_id=res.document_id,
            document_title=res.document_title,
            document_category=res.document_category,
            classification=res.classification,
            page_number=res.page_number,
            section_heading=res.section_heading,
            supporting_excerpt=excerpt,
            similarity_score=res.similarity_score,
        )
        citations.append(cit)

    return citations
