"""Answer generation module for Internal Company Knowledge Assistant.

Generates strictly grounded, evidence-based answers from retrieved document excerpts.
In basic mode, it produces clear, synthesized, and attributed summaries with verbatim policy quotes
without hallucinating or relying on paid external APIs. Designed to be extensible for local LLMs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.citation_service import Citation, build_citations, extract_key_excerpt
from backend.retriever import RetrievalResult

NO_EVIDENCE_MESSAGE = (
    "No sufficient evidence was found in the approved company documents to answer this question. "
    "To prevent misinformation, this assistant does not guess policies, pricing, or procedures. "
    "Please verify if the relevant document has been approved or contact your department administrator."
)


COMMON_STOPWORDS = {
    "what", "where", "when", "which", "who", "whom", "whose", "why", "how",
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
    "with", "by", "from", "up", "about", "into", "over", "after", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "can", "could", "should", "would", "may", "might", "must", "shall",
    "will", "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "there", "here", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "tell", "explain", "give", "please", "company", "information"
}


def evaluate_evidence_sufficiency(
    query: str,
    retrieved_results: List[RetrievalResult],
    min_keyword_overlap_ratio: float = 0.40,
) -> bool:
    """Evaluate whether retrieved chunks contain sufficient substantive evidence to answer the query.

    Prevents spurious answers when a document shares only one incidental common word (e.g. 'office')
    with an otherwise unaddressed question (e.g. 'sales targets for Tokyo office').

    Args:
        query: User question.
        retrieved_results: Chunks retrieved by search.
        min_keyword_overlap_ratio: Minimum fraction of substantive query words that must appear.

    Returns:
        bool: True if sufficient evidence exists, False otherwise.
    """
    raw_tokens = re.findall(r"\b[\w\-]{3,}\b", query.lower())
    substantive_tokens = [t for t in raw_tokens if t not in COMMON_STOPWORDS]

    if not substantive_tokens:
        # If query has only very short or generic words, require reasonable similarity score
        return any(r.similarity_score >= 0.20 for r in retrieved_results)

    combined_chunk_text = " ".join(r.chunk_text.lower() for r in retrieved_results[:3])

    matched_tokens = [t for t in substantive_tokens if t in combined_chunk_text]
    overlap_ratio = len(matched_tokens) / len(substantive_tokens)

    # If query has 3 or more substantive tokens, require at least 2 distinct matched tokens
    # and at least min_keyword_overlap_ratio
    if len(substantive_tokens) >= 3:
        if len(matched_tokens) < 2 or overlap_ratio < min_keyword_overlap_ratio:
            return False
    elif len(substantive_tokens) == 2:
        if len(matched_tokens) < 1 or overlap_ratio < 0.5:
            return False
    else:  # Single substantive keyword
        if len(matched_tokens) < 1:
            return False

    return True


@dataclass
class GeneratedAnswer:
    """The structured answer returned to the user interface."""
    status: str  # 'answered' | 'insufficient_evidence' | 'empty_query'
    answer_text: str
    citations: List[Citation] = field(default_factory=list)
    evidence_count: int = 0
    mode: str = "basic_evidence_synthesis"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "answer_text": self.answer_text,
            "citations": [c.to_dict() for c in self.citations],
            "evidence_count": self.evidence_count,
            "mode": self.mode,
        }


class AnswerGenerator:
    """Produces grounded answers from retrieved context without external APIs."""

    def __init__(self, mode: str = "basic") -> None:
        self.mode = mode

    def generate_answer(
        self,
        query: str,
        retrieved_results: List[RetrievalResult],
        user: Dict[str, Any],
        db_path: Optional[str] = None,
    ) -> GeneratedAnswer:
        """Synthesize an answer strictly from retrieved authorized evidence.

        Args:
            query: User's question.
            retrieved_results: Chunks retrieved by the TF-IDF search engine.
            user: Authenticated user.
            db_path: Optional database path.

        Returns:
            GeneratedAnswer: Grounded answer with citations or explicit no-evidence statement.
        """
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            return GeneratedAnswer(
                status="empty_query",
                answer_text="Please enter a question to search company documentation.",
                citations=[],
                evidence_count=0,
                mode="basic_evidence_synthesis",
            )

        if not retrieved_results:
            return GeneratedAnswer(
                status="insufficient_evidence",
                answer_text=NO_EVIDENCE_MESSAGE,
                citations=[],
                evidence_count=0,
                mode="basic_evidence_synthesis",
            )

        # Verify that retrieved evidence substantively addresses the query
        if not evaluate_evidence_sufficiency(cleaned_query, retrieved_results):
            return GeneratedAnswer(
                status="insufficient_evidence",
                answer_text=NO_EVIDENCE_MESSAGE,
                citations=[],
                evidence_count=0,
                mode="basic_evidence_synthesis",
            )

        # Build authenticated citations
        citations = build_citations(retrieved_results, cleaned_query, user, db_path=db_path)
        if not citations:
            return GeneratedAnswer(
                status="insufficient_evidence",
                answer_text=NO_EVIDENCE_MESSAGE,
                citations=[],
                evidence_count=0,
                mode="basic_evidence_synthesis",
            )

        # Group evidence by document for clear synthesized summary
        doc_groups: Dict[str, List[RetrievalResult]] = {}
        for r in retrieved_results:
            doc_groups.setdefault(r.document_title, []).append(r)

        response_lines: List[str] = []
        response_lines.append("### Summary of Approved Company Information\n")
        response_lines.append(
            f"Based on **{len(retrieved_results)}** verified excerpt(s) across **{len(doc_groups)}** approved document(s), "
            "the following established information was identified:\n"
        )

        # Synthesize key findings
        for doc_title, items in doc_groups.items():
            top_item = items[0]
            section_info = f" (Section: {top_item.section_heading})" if top_item.section_heading else ""
            page_info = f", Page {top_item.page_number}" if top_item.page_number else ""
            source_tag = f"**From: {doc_title}{section_info}{page_info}**"

            response_lines.append(f"{source_tag}")

            # Extract key sentences matching the query
            key_excerpt = extract_key_excerpt(top_item.chunk_text, cleaned_query, max_words=70)
            response_lines.append(f"> \"{key_excerpt}\"\n")

            # Check for pricing figures, percentages, or explicit condition terms
            conditions = re.findall(
                r"(?:(?:tier|level|step|\$|€|£|usd|inr|\d+%)[\w\.\s\$,\-\/]+|\b(?:must|shall|required|eligible|excluding|exception|sla|deadline)\b[^\.\n]+[\.\n])",
                top_item.chunk_text,
                flags=re.IGNORECASE,
            )
            if conditions:
                clean_conds = [c.strip() for c in conditions[:2] if len(c.strip()) > 10]
                if clean_conds:
                    response_lines.append("**Key Terms & Conditions:**")
                    for c in clean_conds:
                        response_lines.append(f"- {c}")
                    response_lines.append("")

        response_lines.append(
            "_Note: This response is strictly constructed from authorized, approved company documents. "
            "Please consult the cited sources below for complete contextual specifications._"
        )

        return GeneratedAnswer(
            status="answered",
            answer_text="\n".join(response_lines),
            citations=citations,
            evidence_count=len(retrieved_results),
            mode="basic_evidence_synthesis",
        )
