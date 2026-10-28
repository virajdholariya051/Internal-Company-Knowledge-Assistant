"""TF-IDF retrieval engine for Internal Company Knowledge Assistant.

Builds a TF-IDF index across all approved document chunks, ranks candidate chunks
using cosine similarity, and enforces document-level and classification-level
access authorization before returning candidates to the answer generator.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.access_control import get_authorized_document_ids
from backend.database import get_db_connection

DEFAULT_TOP_K = 5
DEFAULT_MIN_RELEVANCE_SCORE = 0.12


@dataclass
class RetrievalResult:
    """Represents a retrieved chunk with similarity score and citation metadata."""
    chunk_id: str
    document_id: str
    document_title: str
    document_category: str
    classification: str
    chunk_text: str
    page_number: Optional[int]
    section_heading: Optional[str]
    similarity_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_title": self.document_title,
            "document_category": self.document_category,
            "classification": self.classification,
            "chunk_text": self.chunk_text,
            "page_number": self.page_number,
            "section_heading": self.section_heading,
            "similarity_score": round(self.similarity_score, 4),
        }


class TFIDFRetriever:
    """Manages the TF-IDF vector space index and similarity search."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        # Vectorizer preserves alphanumeric tokens, currency signs, percentages, and hyphenated terms
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
            token_pattern=r"(?u)\b[\w\$\%\.\-]+\b",
        )
        self.tfidf_matrix = None
        self.chunk_metadata: List[Dict[str, Any]] = []
        self.is_indexed: bool = False

    def build_index(self) -> int:
        """Rebuild the retrieval index from all approved document chunks in the database.

        Returns:
            int: Number of chunks indexed.
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT c.chunk_id, c.document_id, c.chunk_index, c.chunk_text,
                       c.page_number, c.section_heading,
                       d.title as doc_title, d.category as doc_category,
                       d.classification as doc_classification
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.document_id
                WHERE d.status = 'Approved'
                ORDER BY c.document_id, c.chunk_index ASC;
                """
            )
            rows = cursor.fetchall()

        if not rows:
            self.chunk_metadata = []
            self.tfidf_matrix = None
            self.is_indexed = False
            return 0

        self.chunk_metadata = [dict(row) for row in rows]
        corpus = [
            f"{row['doc_title']} {row['section_heading'] or ''} {row['chunk_text']}"
            for row in self.chunk_metadata
        ]

        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        self.is_indexed = True
        return len(self.chunk_metadata)

    def retrieve(
        self,
        query: str,
        user: Dict[str, Any],
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_RELEVANCE_SCORE,
    ) -> List[RetrievalResult]:
        """Retrieve top relevant chunks matching query that the user is authorized to read.

        Enforces:
        1. User must be active.
        2. Chunks must come from 'Approved' documents.
        3. User must have explicit authorization for Restricted or Confidential documents.
        4. Cosine similarity score must meet or exceed min_score.

        Args:
            query: User's natural language question.
            user: Authenticated user dictionary.
            top_k: Maximum number of chunks to return.
            min_score: Minimum cosine similarity threshold.

        Returns:
            List[RetrievalResult]: Ranked list of matching authorized chunks.
        """
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            return []

        if not self.is_indexed or self.tfidf_matrix is None or len(self.chunk_metadata) == 0:
            # Try building index on demand if not yet initialized
            count = self.build_index()
            if count == 0:
                return []

        # Get set of document IDs authorized for this user
        authorized_doc_ids = get_authorized_document_ids(user, db_path=self.db_path)
        if not authorized_doc_ids:
            return []

        # Transform query vector
        try:
            query_vec = self.vectorizer.transform([cleaned_query])
            scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        except Exception:
            return []

        # Filter candidates by authorization and score threshold
        candidate_indices = np.where(scores >= min_score)[0]
        if len(candidate_indices) == 0:
            return []

        scored_candidates: List[Tuple[int, float]] = []
        for idx in candidate_indices:
            meta = self.chunk_metadata[idx]
            # Security verification: document must be in authorized_doc_ids
            if meta["document_id"] in authorized_doc_ids:
                scored_candidates.append((idx, float(scores[idx])))

        # Sort descending by score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        results: List[RetrievalResult] = []
        for idx, score in scored_candidates[:top_k]:
            meta = self.chunk_metadata[idx]
            res = RetrievalResult(
                chunk_id=meta["chunk_id"],
                document_id=meta["document_id"],
                document_title=meta["doc_title"],
                document_category=meta["doc_category"],
                classification=meta["doc_classification"],
                chunk_text=meta["chunk_text"],
                page_number=meta["page_number"],
                section_heading=meta["section_heading"],
                similarity_score=score,
            )
            results.append(res)

        return results


# Global singleton retriever instance for application lifecycle
_retriever_instance: Optional[TFIDFRetriever] = None


def get_retriever(db_path: Optional[str] = None, force_rebuild: bool = False) -> TFIDFRetriever:
    """Retrieve or initialize the application retriever instance."""
    global _retriever_instance
    if _retriever_instance is None or force_rebuild or (db_path and _retriever_instance.db_path != db_path):
        _retriever_instance = TFIDFRetriever(db_path=db_path)
        _retriever_instance.build_index()
    return _retriever_instance
